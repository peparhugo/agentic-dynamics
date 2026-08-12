import fs from 'fs/promises';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Frontmatter, Page } from '../site-generator';
import { Plugin } from '../plugin';

function normalizeTags(value: Frontmatter['tags']): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function formatDate(value: Frontmatter['date']): string | undefined {
  if (!value) return undefined;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

export const pageFrontmatter = new WeakMap<Page, Frontmatter>();
const pageSources = new WeakMap<Page, string>();

export function setMarkdownSource(page: Page, source: string): void { pageSources.set(page, source); }

export function parseMarkdown(source: string, sourcePath = ''): Page {
  const parsed = matter(source);
  const data = parsed.data as Frontmatter;
  const title = typeof data.title === 'string' && data.title.trim()
    ? data.title.trim() : path.basename(sourcePath, path.extname(sourcePath));
  const page: Page = {
    sourcePath,
    outputPath: sourcePath.replace(/\.md$/i, '.html'),
    title,
    date: formatDate(data.date),
    tags: normalizeTags(data.tags),
    html: marked.parse(parsed.content),
    template: typeof data.template === 'string' ? data.template : undefined,
    layout: typeof data.layout === 'string' ? data.layout : undefined,
  };
  pageFrontmatter.set(page, data);
  return page;
}

export class MarkdownPlugin implements Plugin {
  async onFile(page: Page): Promise<Page> {
    return parseMarkdown(pageSources.get(page) ?? '', page.sourcePath);
  }
}

export async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort();
}
