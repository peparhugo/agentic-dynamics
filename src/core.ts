import fs from 'fs';
import path from 'path';
import { buildIndexHtml, buildPageHtml, pageTitle } from './generator';
import { PluginPipeline } from './plugin';
import type { Plugin, PluginContext } from './plugin';
import type { SiteContext } from './engine';
import type { Page } from './types';
import type { SiteBuildResult } from './build';

export interface SSGEngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  plugins?: Plugin[];
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
  }

  start(): void {
    this.pipeline.runHook('onStart', this.ctx);
  }

  stop(): void {
    this.pipeline.runHook('onEnd', this.ctx);
  }

  build(): SiteBuildResult {
    const { contentDir, outputDir } = this.ctx;

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
    this.ctx.pages = pages;

    this.pipeline.runHook('beforeBuild', this.ctx);

    for (const page of pages) {
      this.pipeline.runHook('onFile', page, this.ctx);
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
      this.pipeline.runHook('onFile', page, this.ctx);
    }

    for (const page of pages) {
      const html = page.templated ?? buildPageHtml(page);
      fs.writeFileSync(path.join(outputDir, page.outputFile), html, 'utf-8');
    }

    const indexFile = path.join(outputDir, 'index.html');
    fs.writeFileSync(indexFile, buildIndexHtml(pages), 'utf-8');

    const result: SiteBuildResult = { outputDir, pages, indexFile };
    this.ctx.lastResult = result;
    this.pipeline.runHook('afterBuild', this.ctx);
    return result;
  }
}
