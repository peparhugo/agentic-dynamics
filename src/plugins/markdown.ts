import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin } from '../types';

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

export class MarkdownPlugin implements Plugin {
  async onFile(page: Parameters<NonNullable<Plugin['onFile']>>[0]): Promise<void> {
    const parsed = matter(page.source);
    page.frontmatter = parsed.data;
    page.content = parsed.content;
    page.title = typeof parsed.data.title === 'string' ? parsed.data.title : page.title;
    page.date = normalizeDate(parsed.data.date);
    page.tags = normalizeTags(parsed.data.tags);
    page.template = typeof parsed.data.template === 'string' ? parsed.data.template : undefined;
    page.layout = typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined;
    page.html = await marked.parse(parsed.content);
    page.output = page.html;
  }
}
