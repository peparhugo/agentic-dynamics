import matter from 'gray-matter';
import { marked } from 'marked';
import { Frontmatter } from './types';

export function parseFrontmatter(source: string): Frontmatter & { body: string } {
  const parsed = matter(source);
  const data = (parsed.data ?? {}) as Record<string, unknown>;

  const title = typeof data.title === 'string' ? data.title.trim() : undefined;
  const date =
    typeof data.date === 'string' || typeof data.date === 'number' || data.date instanceof Date
      ? new Date(data.date as string | number | Date).toISOString()
      : undefined;

  let tags: string[] = [];
  if (Array.isArray(data.tags)) {
    tags = data.tags
      .filter((t): t is string => typeof t === 'string')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
  } else if (typeof data.tags === 'string') {
    tags = data.tags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
  }

  return { title, date, tags, body: parsed.content };
}

export async function renderMarkdown(markdown: string): Promise<string> {
  const html = await marked.parse(markdown);
  return html;
}
