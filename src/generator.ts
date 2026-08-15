import * as fs from 'fs';
import * as path from 'path';
import { parseFrontmatter } from './frontmatter';
import { renderMarkdown, renderPageHtml, renderIndexHtml } from './render';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;

  if (!fs.existsSync(contentDir) || !fs.statSync(contentDir).isDirectory()) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const markdownFiles = findMarkdownFiles(contentDir);
  const pages = markdownFiles.map((filePath) => buildPage(filePath, contentDir));
  pages.sort(comparePages);

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const outPath = path.join(outputDir, page.outputFile);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, renderPageHtml(page), 'utf8');
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndexHtml(pages), 'utf8');

  return { pages, outputDir };
}

function comparePages(a: Page, b: Page): number {
  if (a.date && b.date) return b.date.localeCompare(a.date);
  if (a.date) return -1;
  if (b.date) return 1;
  return a.title.localeCompare(b.title);
}

function findMarkdownFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }

  return files;
}

function buildPage(filePath: string, contentDir: string): Page {
  const raw = fs.readFileSync(filePath, 'utf8');
  const { data, content } = parseFrontmatter(raw);
  const html = renderMarkdown(content);

  const relativePath = path.relative(contentDir, filePath);
  const slug = slugify(relativePath);
  const title = typeof data.title === 'string' && data.title.trim() ? data.title : slug;
  const date = typeof data.date === 'string' && data.date.trim() ? data.date : undefined;
  const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];

  return {
    slug,
    title,
    date,
    tags,
    html,
    sourcePath: relativePath,
    outputFile: `${slug}.html`,
  };
}

function slugify(relativePath: string): string {
  const withoutExt = relativePath.replace(/\.md$/i, '');
  const slug = withoutExt
    .split(path.sep)
    .join('-')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

  // "index" is reserved for the generated listing page.
  if (!slug || slug === 'index') return slug === 'index' ? 'index-page' : 'page';
  return slug;
}
