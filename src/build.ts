import fs from 'fs';
import path from 'path';
import { parseFrontmatter } from './frontmatter';
import { renderMarkdown } from './markdown';
import { renderIndexTemplate, renderPageTemplate } from './templates';
import { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

function slugify(filename: string): string {
  return filename.replace(/\.md$/i, '');
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) return tags.map((tag) => String(tag));
  if (typeof tags === 'string' && tags.length > 0) return [tags];
  return [];
}

export function findMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }
  return fs
    .readdirSync(contentDir)
    .filter((file) => file.toLowerCase().endsWith('.md'))
    .sort();
}

export function buildPage(contentDir: string, filename: string): Page {
  const filePath = path.join(contentDir, filename);
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = parseFrontmatter(raw);
  const body = renderMarkdown(content);
  const slug = slugify(filename);
  const title = typeof data.title === 'string' && data.title.length > 0 ? data.title : slug;
  const date = typeof data.date === 'string' ? data.date : undefined;
  const tags = normalizeTags(data.tags);
  const outputPath = `${slug}.html`;
  const html = renderPageTemplate({ title, date, tags, body });
  return { slug, title, date, tags, html, outputPath };
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const files = findMarkdownFiles(contentDir);
  const pages = files.map((file) => buildPage(contentDir, file));

  fs.mkdirSync(outputDir, { recursive: true });
  for (const page of pages) {
    fs.writeFileSync(path.join(outputDir, page.outputPath), page.html, 'utf-8');
  }
  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndexTemplate(pages), 'utf-8');

  return { pages, outputDir };
}
