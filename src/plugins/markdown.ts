import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from '../generator.js';
import type { BuildContext, Plugin } from '../plugin.js';

function toDateString(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' && value.trim()) return value;
  return undefined;
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function toTemplateName(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  const name = value.trim().replace(/\.hbs$/i, '');
  if (name.includes('/') || name.includes('\\') || name === '.' || name === '..') throw new Error(`Invalid template name: ${value}`);
  return name;
}

export class MarkdownPlugin implements Plugin {
  private static readonly parsedPages = new Map<string, Page>();

  async beforeBuild(context: BuildContext): Promise<void> {
    const entries = await readdir(context.options.contentDir, { withFileTypes: true });
    const markdownFiles = entries.filter((entry) => entry.isFile() && /\.md$/i.test(entry.name));
    context.pages = await Promise.all(markdownFiles.map(async (entry): Promise<Page> => {
      const source = await readFile(path.join(context.options.contentDir, entry.name), 'utf8');
      const slug = entry.name.replace(/\.md$/i, '');
      const sourcePath = path.join(context.options.contentDir, entry.name);
      const sourceHash = createHash('sha256').update(source).digest('hex');
      const cached = MarkdownPlugin.parsedPages.get(sourcePath);
      if (cached?.sourceHash === sourceHash) return { ...cached, data: { ...cached.data } };
      const parsed = matter(source);
      const page: Page = {
        slug,
        title: typeof parsed.data.title === 'string' && parsed.data.title.trim() ? parsed.data.title : slug,
        date: toDateString(parsed.data.date),
        tags: toTags(parsed.data.tags),
        html: await marked.parse(parsed.content),
        template: toTemplateName(parsed.data.template),
        layout: toTemplateName(parsed.data.layout),
        data: parsed.data,
        sourcePath,
        sourceHash
      };
      MarkdownPlugin.parsedPages.set(sourcePath, page);
      return { ...page, data: { ...page.data } };
    }));
    context.pages.sort((left, right) => (right.date ?? '').localeCompare(left.date ?? ''));
  }
}
