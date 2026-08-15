import fs from 'fs';
import path from 'path';
import { parseFrontmatter } from './frontmatter';
import { Page } from './types';
import { Plugin, PluginContext, PageDraft } from './plugin';

function slugify(filename: string): string {
  return filename.replace(/\.md$/i, '');
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) return tags.map((tag) => String(tag));
  if (typeof tags === 'string' && tags.length > 0) return [tags];
  return [];
}

export function findMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }
  return fs
    .readdirSync(contentDir)
    .filter((file) => file.toLowerCase().endsWith('.md'))
    .sort();
}

function makeDraft(contentDir: string, filename: string): PageDraft {
  const filePath = path.join(contentDir, filename);
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = parseFrontmatter(raw);
  const slug = slugify(filename);
  const title = typeof data.title === 'string' && data.title.length > 0 ? data.title : slug;
  const date = typeof data.date === 'string' ? data.date : undefined;
  const tags = normalizeTags(data.tags);
  const outputPath = `${slug}.html`;
  const template =
    typeof data.template === 'string' && data.template.trim().length > 0 ? data.template.trim() : 'default';
  return { slug, filename, data, content, title, date, tags, template, outputPath, body: '', html: '' };
}

function toPage(draft: PageDraft): Page {
  return {
    slug: draft.slug,
    title: draft.title,
    date: draft.date,
    tags: draft.tags,
    html: draft.html,
    outputPath: draft.outputPath,
    template: draft.template,
  };
}

/**
 * Orchestrates the plugin pipeline. `onStart`/`onEnd` bracket the engine's
 * whole lifetime (e.g. a dev server's process); `beforeBuild`/`onFile`/
 * `afterBuild` run once per build pass and stay fully synchronous so the
 * public `buildPage`/`build` API can remain synchronous too.
 */
export class SSGEngine {
  constructor(private readonly plugins: Plugin[]) {}

  async start(ctx: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.onStart?.(ctx);
    }
  }

  async end(ctx: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.onEnd?.(ctx);
    }
  }

  buildFile(contentDir: string, filename: string, ctx: PluginContext): Page {
    const draft = makeDraft(contentDir, filename);
    for (const plugin of this.plugins) {
      plugin.onFile?.(draft, ctx);
    }
    return toPage(draft);
  }

  runBuild(ctx: PluginContext): Page[] {
    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(ctx);
    }
    const files = findMarkdownFiles(ctx.contentDir);
    const pages = files.map((file) => this.buildFile(ctx.contentDir, file, ctx));
    for (const plugin of this.plugins) {
      plugin.afterBuild?.(pages, ctx);
    }
    return pages;
  }
}
