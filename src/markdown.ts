import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({ html: true });

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string | string[];
  template?: string;
  layout?: string;
}

export interface ParsedMarkdown {
  data: Frontmatter;
  body: string;
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const year = value.getUTCFullYear();
    const month = String(value.getUTCMonth() + 1).padStart(2, '0');
    const day = String(value.getUTCDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  if (typeof value === 'string' && value.trim() !== '') return value.trim();
  return undefined;
}

export function parseMarkdown(raw: string): ParsedMarkdown {
  const { data, content } = matter(raw);
  const normalized: Frontmatter = { ...(data as Frontmatter) };
  if (normalized.date !== undefined) {
    normalized.date = normalizeDate(normalized.date);
  }
  return { data: normalized, body: content };
}

export function renderMarkdown(markdown: string): string {
  return md.render(markdown);
}
