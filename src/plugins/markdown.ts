import { readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from '../site';
import type { BuildContext, Plugin } from './plugin';

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string' && value.length > 0) return [value];
  return [];
}

function toDateString(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

export class MarkdownPlugin implements Plugin {
  onFile(page: Page, context: BuildContext): void {
    if (!page.sourcePath) throw new Error('Markdown plugin requires a source path');
    const parsed = matter(readFileSync(page.sourcePath, 'utf8'));
    const relativePath = relative(context.contentDir, page.sourcePath).replace(/\.md$/i, '.html');
    page.url = relativePath.split(sep).join('/');
    page.outputPath = join(context.outputDir, relativePath);
    page.date = toDateString(parsed.data.date);
    page.title = typeof parsed.data.title === 'string' && parsed.data.title.length > 0
      ? parsed.data.title
      : relativePath.replace(/\.html$/i, '');
    page.tags = toStringArray(parsed.data.tags);
    page.html = marked.parse(parsed.content);
    page.template = typeof parsed.data.template === 'string' && parsed.data.template.length > 0 ? parsed.data.template.replace(/\.hbs$/i, '') : undefined;
    page.layout = typeof parsed.data.layout === 'string' && parsed.data.layout.length > 0 ? parsed.data.layout.replace(/\.hbs$/i, '') : undefined;
  }
}
