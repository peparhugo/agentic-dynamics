import matter from 'gray-matter';
import { marked } from 'marked';

marked.setOptions({
  gfm: true,
  headerIds: false,
  mangle: false,
});

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface ParsedMarkdown {
  frontmatter: Frontmatter;
  contentHtml: string;
}

function toDateString(value: unknown): string | undefined {
  if (typeof value === 'string' && value.length > 0) return value;
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString();
  return undefined;
}

function toTags(value: unknown): string[] | undefined {
  if (Array.isArray(value)) {
    return value.map((tag) => String(tag)).filter((tag) => tag.length > 0);
  }
  if (typeof value === 'string' && value.length > 0) {
    return value
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  }
  return undefined;
}

export function parseMarkdown(raw: string): ParsedMarkdown {
  const { data, content } = matter(raw);
  const frontmatter: Frontmatter = {
    title: typeof data.title === 'string' ? data.title : undefined,
    date: toDateString(data.date),
    tags: toTags(data.tags),
    template: typeof data.template === 'string' && data.template.length > 0 ? data.template : undefined,
    layout: typeof data.layout === 'string' && data.layout.length > 0 ? data.layout : undefined,
  };
  const contentHtml = marked.parse(content.trim());
  return { frontmatter, contentHtml };
}
