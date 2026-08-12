import * as fs from 'fs';
import * as path from 'path';
import { loadPlugins } from './config';
import { parseFrontmatter } from './frontmatter';
import { PluginPipeline, type Plugin, type SsgContext } from './plugin';
import type { SiteConfig } from './template';
import type { Page } from './types';
import {
  CACHE_VERSION,
  cacheMatches,
  collectTemplateDependencies,
  deleteCache,
  hashSource,
  readCache,
  templatesUnchanged,
  writeCache,
  type BuildCache,
  type CachePageEntry,
} from './cache';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  siteTitle?: string;
  templatesDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  configPath?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  total: number;
  built: number;
  skipped: number;
  timeSavedMs: number;
}

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
}

export const DEFAULT_CONTENT_DIR = './content';
export const DEFAULT_OUTPUT_DIR = './dist';
export const DEFAULT_TEMPLATES_DIR = './templates';
export const DEFAULT_SITE_TITLE = 'My Static Site';

const MARKDOWN_EXTENSION = /\.(md|markdown)$/i;

export function collectMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) return [];

  const files: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && MARKDOWN_EXTENSION.test(entry.name)) {
        files.push(full);
      }
    }
  };
  walk(contentDir);
  return files.sort();
}

export function slugFor(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath).replace(/\\/g, '/');
  return relative.replace(MARKDOWN_EXTENSION, '');
}

function toSiteConfig(options: BuildOptions): SiteConfig {
  return {
    title: options.siteTitle ?? DEFAULT_SITE_TITLE,
    templatesDir: options.templatesDir ? path.resolve(options.templatesDir) : path.resolve(DEFAULT_TEMPLATES_DIR),
    defaultTemplate: options.defaultTemplate,
    defaultLayout: options.defaultLayout,
  };
}

function createContext(options: BuildOptions): SsgContext {
  return {
    contentDir: path.resolve(options.contentDir),
    outputDir: path.resolve(options.outputDir),
    siteConfig: toSiteConfig(options),
    pages: [],
    options: { ...options },
  };
}

function outputPathFor(context: SsgContext, slug: string): string {
  return path.join(context.outputDir, `${slug}.html`);
}

function removeStaleOutputs(context: SsgContext, kept: Set<string>): void {
  const cache = readCache(context.outputDir);
  if (!cache) return;
  for (const key of Object.keys(cache.pages)) {
    if (kept.has(key)) continue;
    const slug = key.replace(MARKDOWN_EXTENSION, '');
    const output = path.join(context.outputDir, `${slug}.html`);
    if (output === context.outputDir || !output.startsWith(context.outputDir + path.sep)) continue;
    try {
      fs.rmSync(output, { force: true });
    } catch {
      // ignore
    }
  }
}

export class Ssg {
  private readonly pipeline: PluginPipeline;

  constructor(plugins: Plugin[]) {
    this.pipeline = new PluginPipeline(plugins);
  }

  static async create(options: { plugins?: Plugin[]; configPath?: string } = {}): Promise<Ssg> {
    const plugins = options.plugins ?? (await loadPlugins(options.configPath));
    return new Ssg(plugins);
  }

  getPlugins(): Plugin[] {
    return this.pipeline.getPlugins();
  }

  build(options: BuildOptions): Promise<Page[]> {
    return this.run(options, true);
  }

  rebuild(options: BuildOptions): Promise<Page[]> {
    return this.run(options, false, true);
  }

  buildDetailed(options: BuildOptions): Promise<BuildResult> {
    return this.runDetailed(options, true);
  }

  private async run(options: BuildOptions, runStart: boolean, forceIncremental = false): Promise<Page[]> {
    const result = await this.runDetailed(options, runStart, forceIncremental);
    return result.pages;
  }

  private async runDetailed(options: BuildOptions, runStart: boolean, forceIncremental = false): Promise<BuildResult> {
    const context = createContext(options);
    const incremental = options.incremental === true || forceIncremental;
    const clean = options.clean === true;
    const stats: BuildStats = { total: 0, built: 0, skipped: 0, timeSavedMs: 0 };

    if (clean) {
      deleteCache(context.outputDir);
    }

    const cached = incremental && !clean ? readCache(context.outputDir) : null;
    const canReuse = cached !== null && cacheMatches(cached, context);

    if (runStart) {
      await this.pipeline.onStart(context);
    }
    await this.pipeline.beforeBuild(context);

    const files = collectMarkdownFiles(context.contentDir);
    stats.total = files.length;

    const nextPages: Record<string, CachePageEntry> = {};

    for (const file of files) {
      const key = path.relative(context.contentDir, file).replace(/\\/g, '/');
      const source = fs.readFileSync(file, 'utf8');
      const sourceHash = hashSource(source);
      const slug = slugFor(file, context.contentDir);
      const outputPath = outputPathFor(context, slug);
      const prior = canReuse ? cached.pages[key] : undefined;

      let page: Page;
      let entry: CachePageEntry;

      if (
        prior !== undefined &&
        prior.sourceHash === sourceHash &&
        templatesUnchanged(prior.templates, context.siteConfig, {
          template: prior.data.template,
          layout: prior.data.layout,
        })
      ) {
        stats.skipped += 1;
        stats.timeSavedMs += prior.buildMs;
        page = {
          slug,
          link: `${slug}.html`,
          outputPath,
          filePath: file,
          data: prior.data,
          content: prior.content,
          html: prior.html,
          template: prior.data.template,
          layout: prior.data.layout,
        };
        context.pages.push(page);
        fs.mkdirSync(path.dirname(outputPath), { recursive: true });
        fs.writeFileSync(outputPath, prior.html, 'utf8');
        entry = { ...prior };
      } else {
        stats.built += 1;
        const startedAt = Date.now();
        const { data, content } = parseFrontmatter(source);
        page = {
          slug,
          link: `${slug}.html`,
          outputPath,
          filePath: file,
          data,
          content,
          html: '',
          template: data.template,
          layout: data.layout,
        };
        context.pages.push(page);
        await this.pipeline.onFile(page, context);
        let renderedHtml = page.html;
        try {
          if (fs.existsSync(outputPath)) {
            renderedHtml = fs.readFileSync(outputPath, 'utf8');
          }
        } catch {
          // fall back to page.html
        }
        entry = {
          sourceHash,
          templates: collectTemplateDependencies(context.siteConfig, page),
          data,
          content,
          html: renderedHtml,
          buildMs: Date.now() - startedAt,
        };
      }

      nextPages[key] = entry;
    }

    fs.mkdirSync(context.outputDir, { recursive: true });
    await this.pipeline.afterBuild(context);
    await this.pipeline.onEnd(context);

    removeStaleOutputs(context, new Set(Object.keys(nextPages)));

    const manifest: BuildCache = {
      version: CACHE_VERSION,
      contentDir: context.contentDir,
      outputDir: context.outputDir,
      siteTitle: context.siteConfig.title,
      templatesDir: context.siteConfig.templatesDir ?? '',
      defaultTemplate: context.siteConfig.defaultTemplate,
      defaultLayout: context.siteConfig.defaultLayout,
      pages: nextPages,
    };
    writeCache(context.outputDir, manifest);

    return { pages: context.pages, stats };
  }
}

export async function buildSite(options: BuildOptions): Promise<Page[]> {
  const engine = await Ssg.create({ configPath: options.configPath });
  return engine.build(options);
}

export async function buildSiteDetailed(options: BuildOptions): Promise<BuildResult> {
  const engine = await Ssg.create({ configPath: options.configPath });
  return engine.buildDetailed(options);
}
