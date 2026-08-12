import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  [key: string]: unknown;
}

export interface SitePage {
  title: string;
  date?: string;
  tags: string[];
  source: string;
  output: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];

  const files: string[] = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...markdownFiles(entryPath));
    else if (/\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function stringValue(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function tagsValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function pageFromMarkdown(file: string, contentDir: string): SitePage {
  const parsed = matter(fs.readFileSync(file, 'utf8'));
  const data = parsed.data as Frontmatter;
  const relative = path.relative(contentDir, file);
  const output = relative.replace(/\.md$/i, '.html').split(path.sep).join('/');
  const fallbackTitle = path.basename(relative, path.extname(relative));

  return {
    title: stringValue(data.title) ?? fallbackTitle,
    date: stringValue(data.date),
    tags: tagsValue(data.tags),
    source: relative.split(path.sep).join('/'),
    output,
  };
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function indexHtml(pages: SitePage[]): string {
  const items = pages.map((page) => {
    const metadata = page.date ? ` <time>${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.output)}">${escapeHtml(page.title)}</a>${metadata}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html>\n<head><meta charset="utf-8"><title>Index</title></head>\n<body>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n</body>\n</html>\n`;
}

export function buildSite(options: BuildOptions = {}): SitePage[] {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = markdownFiles(contentDir);
  const pages: SitePage[] = [];

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });

  for (const file of files) {
    const parsed = matter(fs.readFileSync(file, 'utf8'));
    const page = pageFromMarkdown(file, contentDir);
    const destination = path.join(outputDir, page.output);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    // The parser's result is the complete page and must not be wrapped again.
    fs.writeFileSync(destination, marked.parse(parsed.content));
    pages.push(page);
  }

  pages.sort((a, b) => a.title.localeCompare(b.title));
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml(pages));
  return pages;
}

export { indexHtml, markdownFiles };
