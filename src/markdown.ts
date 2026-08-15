import matter from 'gray-matter';
import { marked } from 'marked';

import { PageMeta, ParsedMarkdown } from './types';

export function normalizeTags(tags: unknown): string[] {
  if (tags == null) {
    return [];
  }
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag).trim()).filter((tag) => tag.length > 0);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  }
  const value = String(tags).trim();
  return value ? [value] : [];
}

function normalizeDate(date: unknown): string | undefined {
  if (date instanceof Date) {
    return date.toISOString().slice(0, 10);
  }
  if (typeof date === 'string' && date.trim().length > 0) {
    return date.trim();
  }
  return undefined;
}

export function renderMarkdown(content: string): string {
  return marked.parse(content) as string;
}

/**
 * Parse a Markdown document with YAML frontmatter.
 *
 * gray-matter strips the `---` delimited frontmatter and returns the body in
 * `content`. We only ever pass that stripped body to `marked`, so the
 * frontmatter delimiter is never rendered as literal HTML.
 */
export function parseMarkdown(source: string): ParsedMarkdown {
  const { data, content } = matter(source);

  const meta: PageMeta = {
    title: typeof data.title === 'string' ? data.title : '',
    tags: normalizeTags(data.tags),
  };
  const date = normalizeDate(data.date);
  if (date) {
    meta.date = date;
  }

  const html = renderMarkdown(content);

  return { meta, content, html };
}
