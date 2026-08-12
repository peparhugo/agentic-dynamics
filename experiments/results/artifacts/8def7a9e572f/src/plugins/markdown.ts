import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Plugin, Page, BuildOptions } from '../plugin';

export function parseMarkdownFile(filePath: string): Page | null {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const slug = path.basename(filePath, '.md');

  const parsed = marked.parse(content);
  const html = typeof parsed === 'object' && parsed !== null && 'html' in parsed
    ? (parsed as { html: string }).html
    : parsed as string;

  const date = data.date instanceof Date
    ? data.date.toISOString().split('T')[0]
    : data.date || '';

  return {
    title: data.title || slug,
    date,
    tags: data.tags || [],
    content: html,
    slug,
    layout: data.layout || undefined,
    template: data.template || undefined,
  };
}

export function readContentDirectory(contentDir: string): Page[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }

  const entries = fs.readdirSync(contentDir);
  const pages: Page[] = [];

  for (const entry of entries) {
    if (entry.endsWith('.md')) {
      const page = parseMarkdownFile(path.join(contentDir, entry));
      if (page) {
        pages.push(page);
      }
    }
  }

  return pages;
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';
  pages: Page[] = [];

  beforeBuild(options: BuildOptions): void {
    this.pages = readContentDirectory(options.contentDir);
  }

  onFile(page: Page): Page {
    return page;
  }
}
