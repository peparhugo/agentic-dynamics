import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  contentHtml: string;
  source: string;
}

export function slugify(filename: string): string {
  const base = path.basename(filename, path.extname(filename));
  return base
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function parseMarkdown(content: string, source: string): Page {
  const { data, content: body } = matter(content);

  const slug = slugify(source);
  const title = typeof data.title === 'string' && data.title.trim()
    ? data.title
    : slug;

  let date: string | undefined;
  if (typeof data.date === 'string' && data.date.trim()) {
    date = data.date;
  } else if (data.date instanceof Date && !Number.isNaN(data.date.getTime())) {
    date = data.date.toISOString().slice(0, 10);
  }

  let tags: string[] = [];
  if (Array.isArray(data.tags)) {
    tags = data.tags.map((t) => String(t).trim()).filter(Boolean);
  } else if (typeof data.tags === 'string') {
    tags = data.tags.split(',').map((t) => t.trim()).filter(Boolean);
  }

  const contentHtml = marked.parse(body, { async: false }) as string;

  return { slug, title, date, tags, contentHtml, source };
}

export function readMarkdownFile(filePath: string): Page {
  const content = fs.readFileSync(filePath, 'utf8');
  return parseMarkdown(content, path.basename(filePath));
}
