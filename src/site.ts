/**
 * Site building logic: reads Markdown files from the content directory,
 * renders each into its own HTML file, and generates an index.html.
 */

import fs from 'fs';
import path from 'path';

import { parseFrontmatter } from './frontmatter';
import { markdownToHtml } from './markdown';
import { pageTitle, renderIndex, renderPage } from './render';
import type { BuildOptions, Frontmatter, Page } from './types';

/** Strip the file extension to produce a page slug. */
export function slugify(filename: string): string {
  return filename.replace(/\.[^.]+$/, '');
}

function ensureDirectoryExists(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

/** List Markdown files (non-recursive) inside the content directory. */
export function listMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) return [];
  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && /\.md$/i.test(entry.name))
    .map((entry) => entry.name)
    .sort();
}

/** Read and parse a single Markdown file into a Page object. */
export function readPage(fileName: string, contentDir: string): Page {
  const sourcePath = path.join(contentDir, fileName);
  const raw = fs.readFileSync(sourcePath, 'utf8');
  const { data, content } = parseFrontmatter(raw);

  const slug = slugify(fileName);
  const title = pageTitle(data, slug);

  return {
    slug,
    sourcePath,
    outputName: `${slug}.html`,
    title,
    date: data.date,
    tags: normalizePageTags(data),
    html: markdownToHtml(content),
    content,
    raw,
    data,
  };
}

function normalizePageTags(data: Frontmatter): string[] {
  return Array.isArray(data.tags) ? data.tags.map(String) : [];
}

/** Load and parse every Markdown file in the content directory. */
export function loadPages(contentDir: string): Page[] {
  return listMarkdownFiles(contentDir).map((fileName) => readPage(fileName, contentDir));
}

/**
 * Build the site: render every page into its own HTML file inside the
 * output directory, then generate index.html. Returns the built pages.
 */
export function buildSite(options: BuildOptions): Page[] {
  const { contentDir, outputDir } = options;
  ensureDirectoryExists(outputDir);

  const pages = loadPages(contentDir);

  for (const page of pages) {
    const outputPath = path.join(outputDir, page.outputName);
    fs.writeFileSync(outputPath, renderPage(page));
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages));

  return pages;
}
