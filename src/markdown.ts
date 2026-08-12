import { marked } from 'marked';
import { parseFrontmatter, extractTags } from './frontmatter';
import type { Page } from './types';
import { basename } from 'path';

marked.setOptions({ gfm: true, breaks: false });

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown) as string;
}

export function slugify(input: string): string {
  return input
    .replace(/\.md$/i, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'untitled';
}

export function pageFileName(fileName: string): string {
  const base = basename(fileName);
  const slug = slugify(base);
  return `${slug}.html`;
}

export function toDateString(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  return null;
}

export function parsePage(fileName: string, fileContents: string): Page {
  const { content, data } = parseFrontmatter(fileContents);
  const tags = extractTags(data);
  const date = toDateString(data.date);
  return {
    slug: slugify(basename(fileName)),
    title: typeof data.title === 'string' ? data.title : slugify(basename(fileName)),
    date,
    tags,
    contentHtml: markdownToHtml(content),
    raw: fileContents,
    frontmatter: data,
    fileName
  };
}
