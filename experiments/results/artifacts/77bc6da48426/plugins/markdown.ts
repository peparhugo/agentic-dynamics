import fs from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin } from '../src/plugin';
import type { Page, PageMetadata } from '../src/ssg';

function stringValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

function metadata(data: Record<string, unknown>, sourcePath: string): PageMetadata {
  const tagsValue = data.tags;
  const tags = Array.isArray(tagsValue) ? tagsValue.map(String) : typeof tagsValue === 'string'
    ? tagsValue.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  return {
    title: stringValue(data.title) ?? path.basename(sourcePath, path.extname(sourcePath)),
    date: stringValue(data.date), tags, template: stringValue(data.template), layout: stringValue(data.layout),
  };
}

export class MarkdownPlugin implements Plugin {
  async onFile(page: Page): Promise<Page> {
    const parsed = matter(await fs.readFile(page.sourcePath, 'utf8'));
    return { ...page, metadata: metadata(parsed.data as Record<string, unknown>, page.sourcePath), html: await marked.parse(parsed.content) };
  }
}

export default function markdownPlugin(): Plugin { return new MarkdownPlugin(); }
