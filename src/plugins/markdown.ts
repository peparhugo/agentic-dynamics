import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Frontmatter, Page, Plugin } from '../types';

const normalizeDate = (value: unknown): string | undefined => {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' && value.trim()) return value.trim();
  return undefined;
};

const normalizeTags = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((tag): tag is string => typeof tag === 'string').map((tag) => tag.trim()).filter(Boolean);
  }
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
};

const titleFromFilename = (filename: string): string => path.basename(filename, path.extname(filename))
  .split(/[-_]+/)
  .filter(Boolean)
  .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
  .join(' ');

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  parse(source: string, relativePath: string): Page {
    const parsed = matter(source);
    const data = parsed.data as Frontmatter;
    const title = typeof data.title === 'string' && data.title.trim() ? data.title.trim() : titleFromFilename(relativePath);
    const htmlPath = relativePath.replace(/\.md$/i, '.html');
    const outputPath = htmlPath === 'index.html' ? 'index-page.html' : htmlPath;

    return {
      title,
      date: normalizeDate(data.date),
      tags: normalizeTags(data.tags),
      html: marked.parse(parsed.content, { async: false }) as string,
      outputPath,
      url: outputPath.split(path.sep).join('/'),
      template: typeof data.template === 'string' && data.template.trim() ? data.template.trim() : undefined,
      layout: typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : undefined,
      data,
    };
  }
}
