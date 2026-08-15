import { promises as fs } from 'fs';
import path from 'path';
import { parseFrontmatter, normalizeTags } from './frontmatter';
import type { BuildOptions, BuildStats, Page } from './types';
import type { Plugin, PluginContext } from './plugin';
import type { SsgConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import {
  CacheManager,
  computeTemplatesHash,
  hashFile,
  type CachedPage,
} from './cache';

const MARKDOWN_EXT = /\.(md|markdown)$/i;

async function findMarkdownFiles(dir: string): Promise<string[]> {
  const results: string[] = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return results;
  }

  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...(await findMarkdownFiles(full)));
    } else if (entry.isFile() && MARKDOWN_EXT.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

function slugFor(contentDir: string, filePath: string): string {
  const relative = path.relative(contentDir, filePath);
  const withoutExt = relative.replace(MARKDOWN_EXT, '');
  return withoutExt.split(path.sep).join('/');
}

function titleFor(slug: string, data: { title?: string }): string {
  if (data.title && data.title.trim()) {
    return data.title.trim();
  }
  const segments = slug.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? slug;
}

function cachedToPage(cached: CachedPage, sourcePath: string): Page {
  return {
    slug: cached.slug,
    title: cached.title,
    date: cached.date,
    tags: cached.tags,
    contentHtml: cached.contentHtml,
    sourcePath,
    outputPath: cached.outputPath,
    template: cached.template,
    layout: cached.layout,
    data: cached.data,
    content: cached.content,
    html: cached.html,
  };
}

function pageToCache(
  page: Page,
  sourceHash: string,
  templateHash: string,
  buildTimeMs: number
): CachedPage {
  return {
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    contentHtml: page.contentHtml,
    sourcePath: page.sourcePath,
    outputPath: page.outputPath,
    template: page.template,
    layout: page.layout,
    data: page.data,
    content: page.content,
    html: page.html,
    sourceHash,
    templateHash,
    buildTimeMs,
  };
}

export interface EngineOptions extends BuildOptions {
  plugins?: Plugin[];
}

export class SsgEngine {
  readonly options: EngineOptions;
  readonly config: SsgConfig;
  readonly plugins: Plugin[];
  readonly markdown: MarkdownPlugin;
  readonly template: TemplatePlugin;

  private readonly context: PluginContext;
  private pages: Page[] = [];
  private stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };

  constructor(options: EngineOptions, config: SsgConfig, plugins: Plugin[]) {
    this.options = options;
    this.config = config;
    this.markdown = new MarkdownPlugin();
    this.template = new TemplatePlugin(options.templates ?? './templates');
    this.plugins = [this.markdown, this.template, ...plugins];
    this.context = {
      options,
      config,
      cwd: process.cwd(),
    };
  }

  get builtPages(): Page[] {
    return this.pages;
  }

  get buildStats(): BuildStats {
    return { ...this.stats };
  }

  async run(): Promise<Page[]> {
    const ctx = this.context;

    for (const plugin of this.plugins) {
      if (plugin.onStart) {
        await plugin.onStart(ctx);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) {
        await plugin.beforeBuild(ctx);
      }
    }

    const contentDir = path.resolve(this.options.content);
    const outputDir = path.resolve(this.options.output);
    const files = (await findMarkdownFiles(contentDir)).sort();

    const incremental = this.options.incremental === true;
    const clean = this.options.clean === true;

    const cache = new CacheManager(outputDir);
    if (clean) {
      await cache.clear();
    }
    const manifest = incremental ? await cache.load() : undefined;
    const templatesHash = incremental
      ? await computeTemplatesHash(this.options.templates ?? './templates')
      : '';

    this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };

    const pages: Page[] = [];
    const nextPages: Record<string, CachedPage> = {};

    for (const file of files) {
      const started = Date.now();
      const sourceHash = await hashFile(file);
      const cached = manifest?.pages[file];

      const sourceChanged = !cached || cached.sourceHash !== sourceHash;
      const templateChanged = !cached || cached.templateHash !== templatesHash;

      if (incremental && cached && !sourceChanged && !templateChanged) {
        const page = cachedToPage(cached, file);
        pages.push(page);
        nextPages[file] = cached;
        this.stats.pagesSkipped += 1;
        this.stats.timeSavedMs += cached.buildTimeMs ?? 0;
        continue;
      }

      let page: Page;
      if (incremental && cached && !sourceChanged) {
        page = cachedToPage(cached, file);
        page.html = this.template.renderPage(page);
      } else {
        const raw = await fs.readFile(file, 'utf8');
        const { data, body } = parseFrontmatter(raw);
        const slug = slugFor(contentDir, file);

        let built: Page = {
          slug,
          title: titleFor(slug, data),
          date: data.date,
          tags: normalizeTags(data.tags),
          contentHtml: '',
          content: body,
          sourcePath: file,
          outputPath: path.join(outputDir, `${slug}.html`),
          template: data.template,
          layout: data.layout,
          data,
        };

        for (const plugin of this.plugins) {
          if (plugin.onFile) {
            const result = await plugin.onFile(built, ctx);
            if (result) {
              built = result;
            }
          }
        }

        built.html = this.renderPageHtml(built);
        page = built;
      }

      const buildTimeMs = Date.now() - started;
      this.stats.pagesBuilt += 1;
      pages.push(page);
      nextPages[file] = pageToCache(page, sourceHash, templatesHash, buildTimeMs);
    }

    this.pages = pages;

    await fs.mkdir(outputDir, { recursive: true });

    for (const page of pages) {
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      const html = page.html ?? this.renderPageHtml(page);
      await fs.writeFile(page.outputPath, html, 'utf8');
    }

    await fs.writeFile(
      path.join(outputDir, 'index.html'),
      this.template.renderIndex(pages),
      'utf8'
    );

    if (incremental) {
      await cache.save({
        version: 1,
        templatesHash,
        pages: nextPages,
      });
    }

    for (const plugin of this.plugins) {
      if (plugin.afterBuild) {
        await plugin.afterBuild(pages, ctx);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.onEnd) {
        await plugin.onEnd(ctx);
      }
    }

    return pages;
  }

  private renderPageHtml(page: Page): string {
    return page.html ?? this.template.renderPage(page);
  }
}
