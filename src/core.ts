import fs from 'fs';
import path from 'path';
import { buildIndexHtml, buildPageHtml, pageTitle } from './generator';
import { PluginPipeline } from './plugin';
import type { Plugin, PluginContext } from './plugin';
import type { SiteContext } from './engine';
import type { Page } from './types';
import type { SiteBuildResult } from './build';
import {
  CACHE_FILE,
  CACHE_VERSION,
  computeTemplateHash,
  hashContent,
  loadCache,
  saveCache,
} from './cache';
import type { BuildCache, BuildStats, CacheEntry } from './cache';

export interface SSGEngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export function slugify(fileName: string): string {
  const slug = fileName
    .toLowerCase()
    .replace(/\.[^.]+$/, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'page';
}

export class SSGEngine {
  readonly ctx: PluginContext;
  private readonly pipeline: PluginPipeline;
  private readonly incremental: boolean;
  private readonly clean: boolean;

  constructor(options: SSGEngineOptions) {
    const ctx: PluginContext = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir ?? 'templates',
      pages: [],
    };
    ctx.rebuild = () => this.build();
    this.ctx = ctx;
    this.pipeline = new PluginPipeline(options.plugins ?? []);
    this.incremental = options.incremental ?? false;
    this.clean = options.clean ?? false;
  }

  start(): void {
    this.pipeline.runHook('onStart', this.ctx);
  }

  stop(): void {
    this.pipeline.runHook('onEnd', this.ctx);
  }

  build(): SiteBuildResult {
    const { contentDir, outputDir } = this.ctx;
    const startedAt = process.hrtime.bigint();

    if (!fs.existsSync(contentDir)) {
      throw new Error(`content directory not found: ${contentDir}`);
    }

    const mdFiles = fs
      .readdirSync(contentDir)
      .filter((file) => {
        if (!fs.statSync(path.join(contentDir, file)).isFile()) return false;
        return file.toLowerCase().endsWith('.md');
      })
      .sort();

    if (mdFiles.length === 0) {
      throw new Error(`no markdown files found in: ${contentDir}`);
    }

    fs.mkdirSync(outputDir, { recursive: true });

    const pages: Page[] = mdFiles.map((file) => {
      const slug = slugify(file);
      return {
        slug,
        sourcePath: file,
        data: {},
        body: '',
        html: '',
        outputFile: slug === 'index' ? 'index-page.html' : `${slug}.html`,
      };
    });

    const cachePath = path.join(outputDir, CACHE_FILE);
    const useIncremental = this.incremental && !this.clean;
    const previousCache: BuildCache | null = useIncremental ? loadCache(cachePath) : null;
    const templateHash = computeTemplateHash(this.ctx.templatesDir ?? 'templates');

    const cleanFiles = new Set<string>();
    const cachedEntries = new Map<string, CacheEntry>();
    const sourceHashes = new Map<string, string>();

    for (const page of pages) {
      const sourceHash = hashContent(
        fs.readFileSync(path.join(contentDir, page.sourcePath), 'utf-8'),
      );
      sourceHashes.set(page.sourcePath, sourceHash);
      const entry = previousCache?.entries[page.sourcePath];
      if (entry && entry.sourceHash === sourceHash && previousCache.templateHash === templateHash) {
        cleanFiles.add(page.sourcePath);
        cachedEntries.set(page.sourcePath, entry);
        page.data = entry.data;
        page.body = entry.body;
        page.html = entry.html;
        page.templated = entry.outputHtml;
      }
    }

    this.ctx.pages = pages;

    this.pipeline.runHook('beforeBuild', this.ctx);

    for (const page of pages) {
      if (!cleanFiles.has(page.sourcePath)) {
        this.pipeline.runHook('onFile', page, this.ctx);
      }
    }

    pages.sort((a, b) => {
      const dateA = a.data.date ? String(a.data.date) : '';
      const dateB = b.data.date ? String(b.data.date) : '';
      if (dateA !== dateB) {
        return dateA > dateB ? -1 : 1;
      }
      return a.slug.localeCompare(b.slug);
    });

    const site: SiteContext = {
      pages: pages.map((page) => ({
        slug: page.slug,
        title: pageTitle(page.data, page.slug),
        outputFile: page.outputFile,
        date: page.data.date !== undefined ? String(page.data.date) : undefined,
      })),
    };
    this.ctx.site = site;

    for (const page of pages) {
      if (!cleanFiles.has(page.sourcePath)) {
        this.pipeline.runHook('onFile', page, this.ctx);
      }
    }

    for (const page of pages) {
      const html = page.templated ?? buildPageHtml(page);
      const target = path.join(outputDir, page.outputFile);
      if (cleanFiles.has(page.sourcePath) && fs.existsSync(target)) {
        continue;
      }
      fs.writeFileSync(target, html, 'utf-8');
    }

    const indexFile = path.join(outputDir, 'index.html');
    fs.writeFileSync(indexFile, buildIndexHtml(pages), 'utf-8');

    let builtPages = 0;
    let skippedPages = 0;
    const entries: Record<string, CacheEntry> = {};
    for (const page of pages) {
      if (cleanFiles.has(page.sourcePath)) {
        skippedPages += 1;
        entries[page.sourcePath] = cachedEntries.get(page.sourcePath)!;
      } else {
        builtPages += 1;
        entries[page.sourcePath] = {
          sourceHash: sourceHashes.get(page.sourcePath)!,
          data: page.data,
          body: page.body,
          html: page.html,
          outputHtml: page.templated ?? buildPageHtml(page),
        };
      }
    }
    saveCache(cachePath, { version: CACHE_VERSION, templateHash, entries });

    const elapsedMs = Number(process.hrtime.bigint() - startedAt) / 1e6;
    const totalPages = pages.length;
    const timeSavedMs =
      skippedPages > 0 ? Math.max(1, Math.round((elapsedMs * skippedPages) / totalPages)) : 0;
    const stats: BuildStats = {
      totalPages,
      builtPages,
      skippedPages,
      incremental: useIncremental,
      cached: previousCache !== null,
      elapsedMs,
      timeSavedMs,
    };

    const result: SiteBuildResult = { outputDir, pages, indexFile, stats };
    this.ctx.lastResult = result;
    this.pipeline.runHook('afterBuild', this.ctx);
    return result;
  }
}
