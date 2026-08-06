import { readFile, readdir } from 'node:fs/promises';
import { join, extname, relative } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page, Frontmatter } from './types.js';
import { highlightCode } from './highlight.js';

export async function parseMarkdownFiles(sourceDir: string): Promise<Page[]> {
  const pages: Page[] = [];
  await walkDir(sourceDir, sourceDir, pages);
  return pages;
}

async function walkDir(
  dir: string,
  sourceDir: string,
  pages: Page[],
): Promise<void> {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      await walkDir(fullPath, sourceDir, pages);
    } else if (entry.isFile() && extname(entry.name) === '.md') {
      const page = await parseFile(fullPath, sourceDir);
      if (page) pages.push(page);
    }
  }
}

export async function parseFile(
  filePath: string,
  sourceDir: string,
): Promise<Page | null> {
  const raw = await readFile(filePath, 'utf-8');
  const { data, content } = matter(raw);

  if (data.draft === true) return null;

  const html = await marked.parse(content, {
    async: false,
  });

  const relPath = relative(sourceDir, filePath);
  const url =
    '/' +
    relPath.replace(/\.md$/, '.html').replace(/\\/g, '/');

  return {
    path: filePath,
    frontmatter: data as Frontmatter,
    content,
    html,
    url,
  };
}
