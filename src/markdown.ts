import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from './types';
import { hashFile } from './cache';
import type { BuildCache } from './cache';

marked.setOptions({ gfm: true, headerIds: false });

export const DEFAULT_CONTENT_DIR = './content';

export const FRONTMATTER_DELIMITERS: [string, string] = ['<!--', '-->'];

export function parseMarkdown(raw: string, slug: string): Page {
  const { data, content } = matter(raw, { delimiters: FRONTMATTER_DELIMITERS });

  const title = typeof data.title === 'string' && data.title.trim() !== ''
    ? data.title
    : slug;

  let date: string | undefined;
  if (data.date !== undefined && data.date !== null && String(data.date).trim() !== '') {
    date = data.date instanceof Date
      ? data.date.toISOString().slice(0, 10)
      : String(data.date);
  }

  const tags = Array.isArray(data.tags)
    ? data.tags.map((tag: unknown) => String(tag))
    : [];

  const template =
    typeof data.template === 'string' && data.template.trim() !== ''
      ? data.template.trim()
      : undefined;
  const layout =
    typeof data.layout === 'string' && data.layout.trim() !== ''
      ? data.layout.trim()
      : undefined;

  const html = marked.parse(content) as string;

  return { slug, title, date, tags, html, markdown: content, data, template, layout };
}

/**
 * Read every `.md` file from the content directory. When a `cache` manifest is
 * provided, pages whose source hash matches a cached entry are restored from
 * the cache instead of being re-parsed (cached frontmatter + markdown).
 */
export function readPages(contentDir: string, cache?: BuildCache | null): Page[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.md'))
    .sort((a, b) => a.name.localeCompare(b.name));

  return files.map((entry) => {
    const slug = path.basename(entry.name, path.extname(entry.name));
    const filePath = path.join(contentDir, entry.name);
    const sourceHash = hashFile(filePath);

    const cachedEntry = cache?.entries?.[slug];
    if (cachedEntry && cachedEntry.sourceHash === sourceHash && cachedEntry.page) {
      return { ...cachedEntry.page, slug };
    }

    const raw = fs.readFileSync(filePath, 'utf8');
    const page = parseMarkdown(raw, slug);
    page.sourceHash = sourceHash;
    return page;
  });
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    if (a.date && b.date) return b.date.localeCompare(a.date);
    if (a.date) return -1;
    if (b.date) return 1;
    return 0;
  });
}
