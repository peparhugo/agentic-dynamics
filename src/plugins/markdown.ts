import matter from 'gray-matter';
import { marked } from 'marked';
import { pageSources } from '../engine';
import type { Plugin } from '../plugin';
import type { Frontmatter } from '../types';

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' && value.trim()) return value.trim();
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((tag) => tag.trim()).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function templateName(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: import('../types').Page): Promise<void> {
    const parsed = matter(pageSources.get(page) ?? '');
    const frontmatter = parsed.data as Frontmatter;
    page.title = typeof frontmatter.title === 'string' && frontmatter.title.trim()
      ? frontmatter.title.trim()
      : page.title;
    page.date = normalizeDate(frontmatter.date);
    page.tags = normalizeTags(frontmatter.tags);
    page.html = await marked.parse(parsed.content);
    page.data = frontmatter;
    page.template = templateName(frontmatter.template);
    page.layout = templateName(frontmatter.layout);
  }
}
