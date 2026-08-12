import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import type { Frontmatter, SitePage } from '../index';
import type { Plugin, PluginContext } from '../plugin';

export interface MarkdownPage extends SitePage {
  markdown?: string;
  data?: Frontmatter;
  rendered?: string;
}

function stringValue(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function tagsValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

export class MarkdownPlugin implements Plugin {
  onFile(page: SitePage, context: PluginContext): void {
    const markdownPage = page as MarkdownPage;
    const file = path.join(context.contentDir, page.source);
    const parsed = matter(fs.readFileSync(file, 'utf8'));
    const data = parsed.data as Frontmatter;
    markdownPage.data = data;
    markdownPage.markdown = parsed.content;
    markdownPage.title = stringValue(data.title) ?? page.title;
    markdownPage.date = stringValue(data.date);
    markdownPage.tags = tagsValue(data.tags);
    markdownPage.template = stringValue(data.template);
    markdownPage.layout = stringValue(data.layout);
  }
}

export function pageFromMarkdown(file: string, contentDir: string): SitePage {
  const relative = path.relative(contentDir, file);
  const output = relative.replace(/\.md$/i, '.html').split(path.sep).join('/');
  return {
    title: path.basename(relative, path.extname(relative)),
    tags: [],
    source: relative.split(path.sep).join('/'),
    output,
  };
}
