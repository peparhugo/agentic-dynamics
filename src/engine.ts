import { promises as fs } from 'fs';
import path from 'path';
import { parseFrontmatter, normalizeTags } from './frontmatter';
import type { BuildOptions, Page } from './types';
import type { Plugin, PluginContext } from './plugin';
import type { SsgConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

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

    const pages: Page[] = [];
    for (const file of files) {
      const raw = await fs.readFile(file, 'utf8');
      const { data, body } = parseFrontmatter(raw);
      const slug = slugFor(contentDir, file);

      let page: Page = {
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
          const result = await plugin.onFile(page, ctx);
          if (result) {
            page = result;
          }
        }
      }

      pages.push(page);
    }

    this.pages = pages;

    await fs.mkdir(outputDir, { recursive: true });

    for (const page of pages) {
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      const html = page.html ?? this.template.renderPage(page);
      await fs.writeFile(page.outputPath, html, 'utf8');
    }

    await fs.writeFile(
      path.join(outputDir, 'index.html'),
      this.template.renderIndex(pages),
      'utf8'
    );

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
}
