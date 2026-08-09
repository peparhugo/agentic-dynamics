import fs from 'node:fs';
import path from 'node:path';
import { parseDocument, slugify } from './frontmatter.js';
import { excerptFrom, renderMarkdown } from './markdown.js';
import type { Page } from './types.js';

function walk(dir: string, base = dir): string[] {
  const results: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) results.push(...walk(full, base));
    else results.push(path.relative(base, full));
  }
  return results;
}

/** Compute pretty-URL output path for a markdown source path. */
export function outputPathFor(sourcePath: string, slug?: string): string {
  const dir = path.dirname(sourcePath);
  const stem = slug ?? slugify(path.basename(sourcePath, path.extname(sourcePath)));
  const parts = dir === '.' ? [] : dir.split(path.sep);
  if (stem === 'index') return path.posix.join(...parts, 'index.html');
  return path.posix.join(...parts, stem, 'index.html');
}

export function urlFor(outputPath: string): string {
  const url = `/${outputPath.replace(/index\.html$/, '')}`;
  return url === '/' ? '/' : url;
}

/** Load a single markdown file into a Page. */
export function loadPage(sourceDir: string, relPath: string): Page {
  const raw = fs.readFileSync(path.join(sourceDir, relPath), 'utf8');
  const { frontmatter, body } = parseDocument(raw, relPath);
  const outputPath = outputPathFor(relPath.split(path.sep).join('/'), frontmatter.slug);
  return {
    sourcePath: relPath,
    outputPath,
    url: urlFor(outputPath),
    frontmatter,
    body,
    html: renderMarkdown(body),
    excerpt: frontmatter.description ?? excerptFrom(body),
  };
}

export interface LoadedContent {
  pages: Page[];
  /** Non-markdown files to copy through verbatim (relative paths). */
  assets: string[];
}

/** Scan a source directory for markdown pages and static assets. */
export function loadContent(sourceDir: string, includeDrafts: boolean): LoadedContent {
  if (!fs.existsSync(sourceDir)) {
    throw new Error(`Source directory not found: ${sourceDir}`);
  }
  const pages: Page[] = [];
  const assets: string[] = [];
  for (const rel of walk(sourceDir)) {
    if (/\.(md|markdown)$/i.test(rel)) {
      const page = loadPage(sourceDir, rel);
      if (page.frontmatter.draft && !includeDrafts) continue;
      pages.push(page);
    } else {
      assets.push(rel);
    }
  }
  // Newest first; undated pages sort last, ties broken by title.
  pages.sort((a, b) => {
    const ta = a.frontmatter.date?.getTime() ?? -Infinity;
    const tb = b.frontmatter.date?.getTime() ?? -Infinity;
    if (ta !== tb) return tb - ta;
    return a.frontmatter.title.localeCompare(b.frontmatter.title);
  });
  return { pages, assets };
}
