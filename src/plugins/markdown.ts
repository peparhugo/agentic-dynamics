import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin, PluginPage } from '../plugin';

function formatDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function formatTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';
  private readonly cache = new Map<string, {
    source: string;
    data: Record<string, unknown>;
    title: string;
    date?: string;
    tags: string[];
    content: string;
  }>();

  async onFile(page: PluginPage): Promise<void> {
    const cached = this.cache.get(page.sourcePath);
    if (cached?.source === page.source) {
      page.data = { ...cached.data };
      page.title = cached.title;
      page.date = cached.date;
      page.tags = [...cached.tags];
      page.content = cached.content;
      return;
    }
    const parsed = matter(page.source);
    page.data = parsed.data;
    page.title = typeof parsed.data.title === 'string' ? parsed.data.title : page.title;
    page.date = formatDate(parsed.data.date);
    page.tags = formatTags(parsed.data.tags);
    page.content = await marked.parse(parsed.content);
    this.cache.set(page.sourcePath, {
      source: page.source,
      data: { ...page.data },
      title: page.title,
      date: page.date,
      tags: [...page.tags],
      content: page.content
    });
  }
}
