import matter from 'gray-matter';
import { marked } from 'marked';
import { PageFrontmatter } from './types';

marked.setOptions({ gfm: true });

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    return value.trim();
  }
  return undefined;
}

function normalizeOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((tag) => String(tag).trim()).filter((tag) => tag.length > 0);
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    return value
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  }
  return [];
}

export interface ParsedMarkdown {
  frontmatter: PageFrontmatter;
  contentHtml: string;
}

/** Parses raw markdown (with optional YAML frontmatter) into HTML and structured frontmatter. */
export function parseMarkdown(raw: string, fallbackTitle: string): ParsedMarkdown {
  const { data, content } = matter(raw);

  const frontmatter: PageFrontmatter = {
    title: typeof data.title === 'string' && data.title.trim().length > 0 ? data.title.trim() : fallbackTitle,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    template: normalizeOptionalString(data.template),
    layout: normalizeOptionalString(data.layout),
  };

  const contentHtml = marked.parse(content, { async: false }) as string;

  return { frontmatter, contentHtml };
}
