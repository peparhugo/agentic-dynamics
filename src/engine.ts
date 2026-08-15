import * as fs from 'fs';
import * as path from 'path';
import { Page } from './page';
import { Plugin, PluginContext } from './plugin';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  plugins: Plugin[];
  config?: Record<string, unknown>;
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

  constructor(options: EngineOptions) {
    this.ctx = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      config: options.config ?? {},
    };
    this.plugins = options.plugins;
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
    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(this.ctx);
    }

    const files = findMarkdownFiles(this.ctx.contentDir);
    const pages: Page[] = [];

    for (const file of files) {
      let page = stubPage(this.ctx.contentDir, file);
      for (const plugin of this.plugins) {
        const result = plugin.onFile?.(page, this.ctx);
        if (result) page = result;
      }
      pages.push(page);
    }

    for (const plugin of this.plugins) {
      plugin.afterBuild?.(pages, this.ctx);
    }

    return pages;
  }

  /** Runs a full onStart -> build -> onEnd pass and returns the built pages. */
  run(): Page[] {
    this.start();
    const pages = this.build();
    this.end();
    return pages;
  }
}
