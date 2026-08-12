import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { parseMarkdown, renderMarkdown } from './markdown';
import { SSGEngine } from './engine';
import { collectMarkdownFiles, comparePages, normalizeTags, pageTitle, toSlug } from './render';
import type { Plugin } from './plugin';
import type { BuildResult, Page } from './types';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';

export interface BuildOptions {
  templatesDir?: string;
  plugins?: Plugin[];
  configPath?: string;
  port?: number;
}

export { collectMarkdownFiles, renderPage, renderIndex, toSlug } from './render';

export async function loadPages(contentDir: string): Promise<Page[]> {
  const files = await collectMarkdownFiles(contentDir);
  const pages: Page[] = [];

  for (const file of files) {
    const raw = await readFile(file, 'utf8');
    const { data, body } = parseMarkdown(raw);
    const relative = path.relative(contentDir, file);
    const slug = toSlug(relative);

    pages.push({
      title: (data.title && data.title.trim()) || pageTitle(relative),
      date: (data.date && data.date.trim()) || '',
      tags: normalizeTags(data.tags),
      slug,
      source: relative,
      html: renderMarkdown(body),
      template: typeof data.template === 'string' && data.template.trim() ? data.template.trim() : undefined,
      layout: typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : undefined,
      data: { ...(data as Record<string, unknown>) },
    });
  }

  pages.sort(comparePages);
  return pages;
}

export async function buildSite(contentDir: string, outputDir: string, options: BuildOptions = {}): Promise<BuildResult> {
  const engine = new SSGEngine(options);
  return engine.build(contentDir, outputDir);
}
