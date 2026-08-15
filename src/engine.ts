import { promises as fs } from 'fs';
import * as path from 'path';
import { DEFAULT_CACHE_FILE, SsgCache } from './cache';
import { Plugin, PluginContext, PluginPipeline, SsgConfig } from './plugin';
import { BuildOptions, BuildStats, Page } from './types';

const DEFAULT_TEMPLATES_DIR = 'templates';

const CONTENT_EXTENSIONS = ['.md', '.markdown', '.mdown'];

function slugify(filename: string): string {
  const base = filename.replace(/\.(md|markdown|mdown)$/i, '');
  return base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

async function collectMarkdownFiles(dir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectMarkdownFiles(full)));
    } else if (
      entry.isFile() &&
      CONTENT_EXTENSIONS.includes(path.extname(entry.name).toLowerCase())
    ) {
      files.push(full);
    }
  }
  return files;
}

function makeSlug(file: string, contentDir: string): string {
  const rel = path.relative(contentDir, file);
  const parsed = path.parse(rel);
  const joined = parsed.dir ? path.join(parsed.dir, parsed.name) : parsed.name;
  return slugify(joined.replace(/\\/g, '/'));
}

async function dirExists(dir: string): Promise<boolean> {
  try {
    const stat = await fs.stat(dir);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

/**
 * Core SSG engine.
 *
 * Owns the plugin pipeline and orchestrates the lifecycle hooks:
 * `onStart` -> `beforeBuild` -> `onFile` (per content file) -> `afterBuild`
 * -> write outputs -> `onEnd`. Plugins transform pages and contribute output
 * files; the engine is responsible for discovery, ordering, and writing.
 */
export class SsgEngine {
  private readonly pipeline: PluginPipeline;
  private readonly context: PluginContext;
  private readonly stats: BuildStats = { built: 0, skipped: 0, timeSavedMs: 0 };
  private cache: SsgCache | undefined;

  constructor(plugins: Plugin[], options: BuildOptions, config: SsgConfig = {}) {
    const normalized: BuildOptions = {
      ...options,
      templatesDir: options.templatesDir ?? DEFAULT_TEMPLATES_DIR,
    };
    this.pipeline = new PluginPipeline(plugins);
    this.context = {
      config,
      options: normalized,
      pages: [],
      outputFiles: new Map<string, string>(),
      engine: this,
      stats: this.stats,
    };
  }

  getContext(): PluginContext {
    return this.context;
  }

  /** Build statistics accumulated since the last build/rebuild. */
  getStats(): BuildStats {
    return { ...this.stats };
  }

  private resolveCacheFile(): string {
    return this.context.options.cacheFile ?? path.resolve(process.cwd(), DEFAULT_CACHE_FILE);
  }

  private async beginBuild(): Promise<void> {
    this.stats.built = 0;
    this.stats.skipped = 0;
    this.stats.timeSavedMs = 0;
    this.cache = undefined;
    this.context.cache = undefined;

    if (!this.context.options.incremental) {
      return;
    }
    const cacheFile = this.resolveCacheFile();
    if (this.context.options.clean) {
      this.cache = new SsgCache(cacheFile);
    } else {
      this.cache = await SsgCache.load(cacheFile);
    }
    this.context.cache = this.cache;
  }

  private async finishBuild(): Promise<void> {
    if (this.context.cache) {
      await this.context.cache.save();
    }
  }

  /**
   * Run a full build lifecycle (used by the `build` command).
   */
  async build(): Promise<Page[]> {
    await this.beginBuild();
    await this.pipeline.run('onStart', this.context);
    const pages = await this.collectPages();
    await this.pipeline.run('onEnd', this.context);
    await this.finishBuild();
    await this.writeOutputs();
    return pages;
  }

  /**
   * Rebuild content without running start/end hooks (used by the dev server
   * to refresh the site on file changes).
   */
  async rebuild(): Promise<Page[]> {
    await this.beginBuild();
    const pages = await this.collectPages();
    await this.finishBuild();
    await this.writeOutputs();
    return pages;
  }

  private async collectPages(): Promise<Page[]> {
    this.context.outputFiles.clear();
    await this.pipeline.run('beforeBuild', this.context);
    await this.collectContent();
    await this.pipeline.run('afterBuild', this.context);
    return this.context.pages;
  }

  /**
   * Run the serve lifecycle. The dev-server plugin starts the server during
   * `onStart`; the resulting server handle is returned to the caller.
   */
  async serve(): Promise<unknown> {
    const devPlugin = this.pipeline
      .getPlugins()
      .find((plugin) => plugin.name === 'dev-server') as
      | { getServer(): unknown }
      | undefined;
    if (!devPlugin || typeof devPlugin.getServer !== 'function') {
      throw new Error('dev-server plugin not loaded');
    }
    await this.pipeline.run('onStart', this.context);
    return devPlugin.getServer();
  }

  private async collectContent(): Promise<void> {
    const { contentDir } = this.context.options;
    if (!(await dirExists(contentDir))) {
      throw new Error(`content directory not found: ${contentDir}`);
    }

    const files = await collectMarkdownFiles(contentDir);
    files.sort();

    const pages: Page[] = [];
    for (const file of files) {
      const source = await fs.readFile(file, 'utf8');
      const slug = makeSlug(file, contentDir);
      const page: Page = {
        slug,
        title: slug,
        tags: [],
        content: source,
        html: source,
        sourcePath: file,
      };
      await this.pipeline.run('onFile', page, this.context);
      pages.push(page);
    }

    this.context.pages = pages;
  }

  private async writeOutputs(): Promise<void> {
    const { outputDir } = this.context.options;
    await fs.mkdir(outputDir, { recursive: true });
    for (const [name, content] of this.context.outputFiles) {
      await fs.writeFile(path.join(outputDir, name), content, 'utf8');
    }
  }
}
