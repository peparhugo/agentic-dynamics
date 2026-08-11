import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Plugin, BuildContext } from '../plugin';
import { PageData } from '../types';

function formatDate(date: unknown): string {
  if (date instanceof Date) {
    return date.toISOString().split('T')[0];
  }
  if (typeof date === 'string') {
    const match = date.match(/^\d{4}-\d{2}-\d{2}/);
    if (match) {
      return match[0];
    }
  }
  return '';
}

export function parseFile(filePath: string): PageData {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const file = path.basename(filePath);

  const frontmatter = {
    title: String(data.title || file.replace(/\.md$/, '')),
    date: formatDate(data.date),
    tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
    template: data.template ? String(data.template) : undefined,
    layout: data.layout ? String(data.layout) : undefined,
  };

  const html = marked.parse(content.trim()) as string;
  const slug = file.replace(/\.md$/, '');

  return { slug, frontmatter, content, html };
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: PageData, _ctx: BuildContext): PageData {
    const { data, content } = matter(page.content);

    const file = page.slug + '.md';
    const frontmatter = {
      title: String(data.title || file.replace(/\.md$/, '')),
      date: formatDate(data.date),
      tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
      template: data.template ? String(data.template) : undefined,
      layout: data.layout ? String(data.layout) : undefined,
    };

    const html = marked.parse(content.trim()) as string;

    return {
      slug: page.slug,
      frontmatter,
      content,
      html,
    };
  }
}
