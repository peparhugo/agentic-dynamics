import * as fs from 'fs';
import * as path from 'path';
import type { Plugin, PluginContext, PluginConfig } from './plugin';
import type { Page } from './types';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  plugins: Plugin[];
  config?: PluginConfig;
}

export interface EngineResult {
  pages: Page[];
  outputDir: string;
}

/**
 * Core SSG engine: discovers Markdown files under `contentDir` and drives
 * them through the registered plugins' lifecycle hooks. The engine itself
 * knows nothing about Markdown parsing, templating, or serving -- those
 * behaviors come entirely from the plugins passed in.
 */
export class SsgEngine {
  constructor(private readonly options: EngineOptions) {}

  build(): EngineResult {
    const { contentDir, outputDir, templatesDir, plugins } = this.options;

    if (!fs.existsSync(contentDir) || !fs.statSync(contentDir).isDirectory()) {
      throw new Error(`Content directory not found: ${contentDir}`);
    }

    const ctx: PluginContext = {
      contentDir,
      outputDir,
      templatesDir,
      config: this.options.config ?? {},
    };

    for (const plugin of plugins) plugin.onStart?.(ctx);
    for (const plugin of plugins) plugin.beforeBuild?.(ctx);

    const files = findMarkdownFiles(contentDir);
    const pages = files.map((filePath) => this.buildPage(filePath, contentDir, ctx));
    pages.sort(comparePages);

    for (const plugin of plugins) plugin.afterBuild?.(pages, ctx);
    for (const plugin of plugins) plugin.onEnd?.(ctx);

    return { pages, outputDir };
  }

  private buildPage(filePath: string, contentDir: string, ctx: PluginContext): Page {
    let page = createPageSkeleton(filePath, contentDir);
    for (const plugin of this.options.plugins) {
      const result = plugin.onFile?.(page, ctx);
      if (result) page = result;
    }
    return page;
  }
}

function createPageSkeleton(filePath: string, contentDir: string): Page {
  const relativePath = path.relative(contentDir, filePath);
  const slug = slugify(relativePath);

  return {
    slug,
    title: slug,
    tags: [],
    html: '',
    sourcePath: relativePath,
    outputFile: `${slug}.html`,
  };
}

function comparePages(a: Page, b: Page): number {
  if (a.date && b.date) return b.date.localeCompare(a.date);
  if (a.date) return -1;
  if (b.date) return 1;
  return a.title.localeCompare(b.title);
}

function findMarkdownFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }

  return files;
}

function slugify(relativePath: string): string {
  const withoutExt = relativePath.replace(/\.md$/i, '');
  const slug = withoutExt
    .split(path.sep)
    .join('-')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

  // "index" is reserved for the generated listing page.
  if (!slug || slug === 'index') return slug === 'index' ? 'index-page' : 'page';
  return slug;
}
