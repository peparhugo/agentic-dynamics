import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, Frontmatter } from './types';

export function parseFile(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  let dateStr = '';
  if (data.date instanceof Date) {
    dateStr = data.date.toISOString().split('T')[0];
  } else if (typeof data.date === 'string') {
    dateStr = data.date;
  }

  const frontmatter: Frontmatter = {
    title: data.title || 'Untitled',
    date: dateStr,
    tags: Array.isArray(data.tags) ? data.tags : [],
    template: typeof data.template === 'string' ? data.template : undefined,
    layout: typeof data.layout === 'string' ? data.layout : undefined,
  };

  const html = marked.parse(content) as string;

  const slug = path.basename(filePath, '.md');

  return { frontmatter, html, slug };
}

export function parseDirectory(contentDir: string): Page[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }

  const files = fs.readdirSync(contentDir).filter((f) => f.endsWith('.md'));

  const pages = files.map((file) => parseFile(path.join(contentDir, file)));

  return pages.sort((a, b) => {
    if (!a.frontmatter.date && !b.frontmatter.date) return 0;
    if (!a.frontmatter.date) return 1;
    if (!b.frontmatter.date) return -1;
    return b.frontmatter.date.localeCompare(a.frontmatter.date);
  });
}
