import { promises as fs } from 'node:fs';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin } from './plugin';
import type { Page } from './generator';

export interface Frontmatter {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  template?: unknown;
  layout?: unknown;
  [key: string]: unknown;
}

export const pageMetadata = new WeakMap<Page, Frontmatter>();
const parsedPages = new WeakMap<Page, { data: Frontmatter; content: string; html?: string }>();

export const setParsedPageData = (page: Page, data: Frontmatter, content: string, html?: string): void => {
  parsedPages.set(page, { data, content, html });
};

const normalizeTags = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
};

const normalizeDate = (value: unknown): string | undefined => {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
};

export const MarkdownPlugin: Plugin = {
  async onFile(page) {
    const cached = parsedPages.get(page);
    const parsed = cached ?? matter(await fs.readFile(page.sourcePath, 'utf8'));
    const metadata = parsed.data as Frontmatter;
    pageMetadata.set(page, metadata);
    page.title = typeof metadata.title === 'string' && metadata.title.trim()
      ? metadata.title
      : page.title;
    page.date = normalizeDate(metadata.date);
    page.tags = normalizeTags(metadata.tags);
    page.html = cached?.html ?? marked.parse(parsed.content);
  },
};
