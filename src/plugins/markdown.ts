import { promises as fs } from 'fs';
import * as path from 'path';
import { marked } from 'marked';
import matter from 'gray-matter';

import type { Page } from '../types';
import type { Plugin, PluginContext } from '../plugin';

export function slugify(name: string): string {
  return name
    .replace(/\.md$/i, '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag)).filter((tag) => tag.length > 0);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  }
  return [];
}

export async function listMarkdownFiles(contentDir: string): Promise<string[]> {
  const entries = await fs.readdir(contentDir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(contentDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listMarkdownFiles(fullPath)));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files.sort();
}

export async function parseMarkdownFile(filePath: string): Promise<Page> {
  const raw = await fs.readFile(filePath, 'utf8');
  const parsed = matter(raw);
  const frontmatter = parsed.data ?? {};
  const baseName = path.basename(filePath);
  const slug = slugify(baseName);
  const title =
    typeof frontmatter.title === 'string' && frontmatter.title.trim().length > 0
      ? frontmatter.title.trim()
      : baseName.replace(/\.md$/i, '');
  const rawDate = frontmatter.date;
  const date =
    typeof rawDate === 'string' && rawDate.trim().length > 0
      ? rawDate.trim()
      : rawDate instanceof Date && !isNaN(rawDate.getTime())
        ? rawDate.toISOString().slice(0, 10)
        : undefined;
  const template =
    typeof frontmatter.template === 'string' && frontmatter.template.trim().length > 0
      ? frontmatter.template.trim()
      : undefined;
  const layout =
    typeof frontmatter.layout === 'string' && frontmatter.layout.trim().length > 0
      ? frontmatter.layout.trim()
      : undefined;
  const html = await marked.parse(parsed.content);
  return {
    slug,
    title,
    date,
    tags: normalizeTags(frontmatter.tags),
    content: parsed.content,
    html,
    template,
    layout,
    data: frontmatter,
  };
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  async beforeBuild(ctx: PluginContext): Promise<void> {
    const files = await listMarkdownFiles(ctx.options.contentDir);
    const pages: Page[] = [];
    for (const file of files) {
      pages.push(await parseMarkdownFile(file));
    }
    ctx.pages.push(...pages);
  }
}
