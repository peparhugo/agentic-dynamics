import { basename, extname, relative } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin } from './plugin';

export class MarkdownPlugin implements Plugin {
  async onFile(page, context): Promise<void> {
    const parsed = matter(page.sourceContent ?? await (await import('node:fs/promises')).readFile(page.source, 'utf8'));
    const relativePath = relative(context.options.contentDir, page.source).replace(/\\/g, '/');
    page.slug = relativePath.replace(/\.(md|markdown)$/i, '.html');
    page.title = typeof parsed.data.title === 'string' ? parsed.data.title : basename(page.source, extname(page.source));
    const dateValue = parsed.data.date;
    page.date = dateValue === undefined
      ? undefined
      : dateValue instanceof Date ? dateValue.toISOString().slice(0, 10) : String(dateValue);
    page.tags = Array.isArray(parsed.data.tags) ? parsed.data.tags.map(String) : [];
    page.html = await marked.parse(parsed.content);
    page.data = parsed.data as Record<string, unknown>;
  }
}
