import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Frontmatter, Page } from './types';

export function parseMarkdown(raw: string): { data: Frontmatter; content: string } {
  const { data, content } = matter(raw);
  return { data: data as Frontmatter, content };
}

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}

export function toDate(value: Date | string | undefined): Date {
  if (value instanceof Date) return value;
  if (typeof value === 'string') {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  return new Date(0);
}

export function readMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }
  return fs
    .readdirSync(contentDir)
    .filter((file) => file.endsWith('.md') || file.endsWith('.markdown'))
    .sort();
}

export function buildPage(slug: string, raw: string): Page {
  const { data, content } = parseMarkdown(raw);
  const html = markdownToHtml(content);
  return {
    slug,
    title: typeof data.title === 'string' ? data.title : slug,
    date: toDate(data.date),
    tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
    html,
    template: typeof data.template === 'string' ? data.template : undefined,
    layout: typeof data.layout === 'string' ? data.layout : undefined,
  };
}

export function sortByDate(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => b.date.getTime() - a.date.getTime());
}

export function loadPages(contentDir: string): Page[] {
  const files = readMarkdownFiles(contentDir);
  const pages = files.map((file) => {
    const raw = fs.readFileSync(path.join(contentDir, file), 'utf-8');
    const slug = path.basename(file, path.extname(file));
    return buildPage(slug, raw);
  });
  return sortByDate(pages);
}
