import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { PageData, ParseResult, ParseOptions } from './types';

export function parseFiles({ contentDir }: ParseOptions): ParseResult {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const files = fs.readdirSync(contentDir).filter((f) => f.endsWith('.md'));

  const pages: PageData[] = files.map((file) => {
    const filePath = path.join(contentDir, file);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const { data, content } = matter(raw);

    const frontmatter = {
      title: String(data.title || file.replace(/\.md$/, '')),
      date: formatDate(data.date),
      tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
    };

    const html = marked.parse(content.trim()) as string;
    const slug = file.replace(/\.md$/, '');

    return { slug, frontmatter, content, html };
  });

  return { pages };
}

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
