import fs from 'fs';
import path from 'path';
import { marked } from 'marked';
import { parseMarkdown } from '../frontmatter';
import { hashContent } from '../cache';
import type { BuildCache, CachedPage } from '../cache';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

const MARKDOWN_EXTENSIONS = ['.md', '.markdown'];

/**
 * Built-in plugin that reads Markdown files from the content directory,
 * extracts frontmatter, and renders the body to HTML.
 *
 * During an incremental build it consults the cache: files whose source and
 * template hashes are unchanged are restored from the cache (skipping the
 * frontmatter parse and Markdown render), and marked as `fresh`.
 */
export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: PluginContext): void {
    context.pages = readPages(
      context.options.contentDir,
      context.cache,
      context.templateHash
    );
  }
}

function readPages(
  contentDir: string,
  cache?: BuildCache,
  templateHash?: string
): Page[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const entries = fs.readdirSync(contentDir);
  const pages: Page[] = [];
  const incremental = !!cache && templateHash !== undefined;

  for (const entry of entries.sort()) {
    const ext = path.extname(entry);
    if (!MARKDOWN_EXTENSIONS.includes(ext)) continue;

    const filePath = path.join(contentDir, entry);
    const slug = slugify(entry);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const sourceHash = incremental ? hashContent(raw) : undefined;

    if (incremental && sourceHash) {
      const cached = cache!.getPage(slug);
      if (
        cached &&
        cached.sourceHash === sourceHash &&
        cached.templateHash === templateHash
      ) {
        pages.push(restoreFromCache(cached));
        continue;
      }
    }

    pages.push(parseFile(filePath, raw, slug, sourceHash));
  }

  return pages;
}

function parseFile(filePath: string, raw: string, slug: string, sourceHash?: string): Page {
  const { data, content } = parseMarkdown(raw);

  return {
    slug,
    title: typeof data.title === 'string' && data.title.trim() !== '' ? data.title : slug,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    html: marked.parse(content) as string,
    sourcePath: filePath,
    template: typeof data.template === 'string' && data.template.trim() !== '' ? data.template.trim() : undefined,
    layout: typeof data.layout === 'string' && data.layout.trim() !== '' ? data.layout.trim() : undefined,
    data,
    sourceHash,
  };
}

function restoreFromCache(cached: CachedPage): Page {
  return {
    slug: cached.slug,
    title: cached.title,
    date: cached.date,
    tags: cached.tags,
    html: cached.bodyHtml,
    sourcePath: cached.sourcePath,
    template: cached.template,
    layout: cached.layout,
    data: cached.data,
    fresh: true,
  };
}

function slugify(filename: string): string {
  return path.basename(filename, path.extname(filename));
}

function normalizeDate(date: unknown): string | undefined {
  if (typeof date === 'string') return date;
  if (date instanceof Date && !Number.isNaN(date.getTime())) {
    return date.toISOString().slice(0, 10);
  }
  return undefined;
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag).trim()).filter(Boolean);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [];
}
