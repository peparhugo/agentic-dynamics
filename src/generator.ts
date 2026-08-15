import { promises as fs } from 'fs';
import * as path from 'path';
import { parseMarkdown } from './markdown';
import { renderIndexHtml, renderPageHtml } from './render';
import { BuildOptions, Page } from './types';

const CONTENT_EXTENSIONS = ['.md', '.markdown', '.mdown'];

function slugify(filename: string): string {
  const base = filename.replace(/\.(md|markdown|mdown)$/i, '');
  return base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

async function collectMarkdownFiles(
  dir: string,
  baseDir: string
): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectMarkdownFiles(full, baseDir)));
    } else if (entry.isFile() && CONTENT_EXTENSIONS.includes(path.extname(entry.name).toLowerCase())) {
      files.push(full);
    }
  }
  return files;
}

function makeSlug(file: string, contentDir: string): string {
  const rel = path.relative(contentDir, file);
  const parsed = path.parse(rel);
  const joined = parsed.dir ? path.join(parsed.dir, parsed.name) : parsed.name;
  return slugify(joined.replace(/\\/g, '/'));
}

async function readPages(contentDir: string): Promise<Page[]> {
  if (!(await dirExists(contentDir))) {
    throw new Error(`content directory not found: ${contentDir}`);
  }
  const files = await collectMarkdownFiles(contentDir, contentDir);
  files.sort();
  const pages: Page[] = [];
  for (const file of files) {
    const source = await fs.readFile(file, 'utf8');
    pages.push(parseMarkdown(source, file, makeSlug(file, contentDir)));
  }
  return pages;
}

async function dirExists(dir: string): Promise<boolean> {
  try {
    const stat = await fs.stat(dir);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

export async function build(options: BuildOptions): Promise<Page[]> {
  const { contentDir, outputDir } = options;
  const pages = await readPages(contentDir);
  await fs.mkdir(outputDir, { recursive: true });

  for (const page of pages) {
    const html = renderPageHtml(page);
    await fs.writeFile(path.join(outputDir, `${page.slug}.html`), html, 'utf8');
  }

  const indexHtml = renderIndexHtml(pages);
  await fs.writeFile(path.join(outputDir, 'index.html'), indexHtml, 'utf8');

  return pages;
}
