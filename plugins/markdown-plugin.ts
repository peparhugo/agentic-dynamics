import matter from 'gray-matter';
import { marked } from 'marked';
import { Page } from '../src/types';
import { Plugin } from '../src/plugin';

function normalizeDate(d: unknown): string | undefined {
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  if (typeof d === 'string') return d;
  return undefined;
}

function normalizeTags(t: unknown): string[] | undefined {
  if (Array.isArray(t)) return t.map((v) => String(v));
  return undefined;
}

function normalizeVal(v: unknown): string | undefined {
  if (typeof v === 'string') return v;
  return undefined;
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: Page): void {
    const raw = matter(page.content);

    page.title = String(raw.data.title || page.slug);
    page.date = normalizeDate(raw.data.date);
    page.tags = normalizeTags(raw.data.tags);
    page.template = normalizeVal(raw.data.template);
    page.layout = normalizeVal(raw.data.layout);
    page.content = raw.content;
    page.html = marked.parse(raw.content) as string;
  }
}
