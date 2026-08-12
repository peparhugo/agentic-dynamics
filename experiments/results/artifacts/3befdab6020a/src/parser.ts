import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, Frontmatter } from './types';

const DEFAULT_FRONTMATTER: Frontmatter = {
  title: '',
  date: '',
  tags: [],
};

export function parseMarkdownFiles(contentDir: string): Page[] {
  const resolved = path.resolve(contentDir);
  const dirEntries = fs.readdirSync(resolved, { withFileTypes: true });

  const pages: Page[] = [];

  for (const entry of dirEntries) {
    if (!entry.isFile() || !entry.name.endsWith('.md')) continue;

    const filePath = path.join(resolved, entry.name);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const { data, content } = matter(raw);

    const dateValue = data.date instanceof Date
      ? data.date.toISOString().split('T')[0]
      : typeof data.date === 'string'
        ? data.date
        : DEFAULT_FRONTMATTER.date;

    const frontmatter: Frontmatter = {
      title: typeof data.title === 'string' ? data.title : DEFAULT_FRONTMATTER.title,
      date: dateValue,
      tags: Array.isArray(data.tags) ? data.tags : DEFAULT_FRONTMATTER.tags,
    };

    const html = marked.parse(content) as string;
    const slug = entry.name.replace(/\.md$/, '');

    pages.push({ slug, frontmatter, content, html });
  }

  pages.sort((a, b) => a.frontmatter.title.localeCompare(b.frontmatter.title));

  return pages;
}
