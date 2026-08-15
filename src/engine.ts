import * as fs from 'fs';
import * as path from 'path';
import { hashFile, PageCache } from './cache';
import { Page } from './page';
import { Plugin, PluginContext } from './plugin';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  plugins: Plugin[];
  config?: Record<string, unknown>;
  /** When true, pages whose source and templates are unchanged since the last build are skipped. */
  incremental?: boolean;
  /** When true (with `incremental`), ignores any existing `.ssg-cache.json` and rebuilds every page. */
  clean?: boolean;
  /** Path to the incremental build manifest. Required when `incremental` is true. */
  cachePath?: string;
}

export interface BuildStats {
  built: number;
  skipped: number;
  timeSavedMs: number;
  totalMs: number;
}

function findMarkdownFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    throw new Error(`Content directory not found: ${dir}`);
  }

  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      results.push(fullPath);
    }
  }

  return results.sort();
}

function slugFromPath(contentDir: string, filePath: string): string {
  const relative = path.relative(contentDir, filePath);
  const withoutExt = relative.replace(/\.md$/i, '');
  return withoutExt.split(path.sep).join('/');
}

function stubPage(contentDir: string, filePath: string): Page {
  const slug = slugFromPath(contentDir, filePath);
  return {
    slug,
    title: '',
    date: null,
    tags: [],
    html: '',
    sourcePath: filePath,
    outputPath: `${slug}.html`,
    template: '',
    layout: '',
  };
}

/**
 * Orchestrates the plugin pipeline: discovers content files and runs every
 * registered plugin's hooks in registration order. Plugins own everything
 * about how a file becomes output (parsing, rendering, writing) - the
 * engine only owns discovery and hook sequencing.
 */
export class SSGEngine {
  readonly ctx: PluginContext;

  private readonly plugins: Plugin[];

  private readonly incremental: boolean;

  private readonly clean: boolean;

  private readonly cachePath: string | undefined;

  /** Stats from the most recent `build()` call, or null when not running in incremental mode. */
  lastBuildStats: BuildStats | null = null;

  constructor(options: EngineOptions) {
    this.ctx = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      config: options.config ?? {},
    };
    this.plugins = options.plugins;
    this.incremental = options.incremental ?? false;
    this.clean = options.clean ?? false;
    this.cachePath = options.cachePath;

    if (this.incremental && !this.cachePath) {
      throw new Error('SSGEngine: `cachePath` is required when `incremental` is true');
    }
  }

  start(): void {
    for (const plugin of this.plugins) {
      plugin.onStart?.(this.ctx);
    }
  }

  end(): void {
    for (const plugin of this.plugins) {
      plugin.onEnd?.(this.ctx);
    }
  }

  build(): Page[] {
    const buildStart = Date.now();

    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(this.ctx);
    }

    const files = findMarkdownFiles(this.ctx.contentDir);
    const pages: Page[] = [];

    const cache = this.incremental
      ? new PageCache(this.cachePath as string, this.ctx.templatesDir, this.clean)
      : null;
    const liveSources = new Set<string>();
    let built = 0;
    let skipped = 0;
    let timeSavedMs = 0;

    for (const file of files) {
      liveSources.add(file);

      if (cache) {
        const sourceHash = hashFile(file);
        const cached = cache.get(file);
        const cachedOutputPath = cached ? path.join(this.ctx.outputDir, cached.outputPath) : '';

        if (cached && cached.sourceHash === sourceHash && fs.existsSync(cachedOutputPath)) {
          pages.push(cached.page);
          skipped += 1;
          timeSavedMs += cached.buildTimeMs;
          continue;
        }

        const pageStart = Date.now();
        const page = this.runFile(file);
        pages.push(page);
        built += 1;
        cache.set(file, { sourceHash, outputPath: page.outputPath, page, buildTimeMs: Date.now() - pageStart });
      } else {
        pages.push(this.runFile(file));
      }
    }

    for (const plugin of this.plugins) {
      plugin.afterBuild?.(pages, this.ctx);
    }

    if (cache) {
      cache.prune(liveSources);
      cache.save();
      this.lastBuildStats = { built, skipped, timeSavedMs, totalMs: Date.now() - buildStart };
    } else {
      this.lastBuildStats = null;
    }

    return pages;
  }

  private runFile(file: string): Page {
    let page = stubPage(this.ctx.contentDir, file);
    for (const plugin of this.plugins) {
      const result = plugin.onFile?.(page, this.ctx);
      if (result) page = result;
    }
    return page;
  }

  /** Runs a full onStart -> build -> onEnd pass and returns the built pages. */
  run(): Page[] {
    this.start();
    const pages = this.build();
    this.end();
    return pages;
  }
}
