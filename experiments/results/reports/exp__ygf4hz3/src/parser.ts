import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { Marked } from 'marked';
import { setupHighlighting } from './highlight';
import { Frontmatter, Page } from './types';

const marked = new Marked();
setupHighlighting(marked);

export function parseMarkdownFile(filePath: string, sourceDir: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  const html = marked.parse(content) as string;

  const relativePath = path.relative(sourceDir, filePath);
  const url =
    '/' +
    relativePath
      .replace(/\.md$/, '.html')
      .replace(/index\.html$/, '')
      .replace(/\\/g, '/');

  if (!data.title) {
    const name = path.basename(filePath, '.md');
    data.title = name.charAt(0).toUpperCase() + name.slice(1);
  }

  return {
    path: relativePath,
    url: url || '/',
    frontmatter: data as Frontmatter,
    content,
    html,
  };
}

export function parseAllMarkdown(sourceDir: string, includeDrafts = false): Page[] {
  const pages: Page[] = [];

  function walk(dir: string) {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!entry.name.startsWith('.') && !entry.name.startsWith('_')) {
          walk(fullPath);
        }
      } else if (entry.name.endsWith('.md')) {
        const page = parseMarkdownFile(fullPath, sourceDir);
        if (!page.frontmatter.draft || includeDrafts) {
          pages.push(page);
        }
      }
    }
  }

  walk(sourceDir);

  return pages.sort((a, b) => {
    const dateA = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const dateB = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return dateB - dateA;
  });
}
