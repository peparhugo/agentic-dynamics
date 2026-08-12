import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import type { Page } from './types';
import { DEFAULT_LAYOUT, DEFAULT_TEMPLATE } from './templates';
import type { TemplateSet } from './templates';

export const CACHE_FILE = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CacheEntry {
  /** sha256 of the raw Markdown source file. */
  sourceHash: string;
  /** sha256 of the template/layout/partial sources used to render the page. */
  templateHash: string;
  /** Rendered HTML for the page, reused when nothing changed. */
  html?: string;
  /** The fully parsed page (frontmatter + markdown), reused to skip parsing. */
  page?: Page;
  /** How long rendering this page took, used to report time saved later. */
  buildMs?: number;
  builtAt?: string;
}

export interface BuildCache {
  version: number;
  generatedAt: string;
  /** Template hash that the current index.html was rendered with. */
  indexHash?: string;
  /** Rendered index.html, reused when nothing changed. */
  indexHtml?: string;
  /** How long rendering the index took, used to report time saved later. */
  indexBuildMs?: number;
  /** Number of pages the index was rendered with. */
  pageCount?: number;
  entries: Record<string, CacheEntry>;
}

export interface BuildStats {
  /** Total number of pages in the site. */
  pages: number;
  /** Pages that were rebuilt during this run. */
  pagesBuilt: number;
  /** Pages that were skipped because their source and template were unchanged. */
  pagesSkipped: number;
  /** Estimated milliseconds saved by skipping unchanged pages. */
  timeSavedMs: number;
}

export function emptyStats(): BuildStats {
  return { pages: 0, pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
}

export function emptyCache(): BuildCache {
  return { version: CACHE_VERSION, generatedAt: new Date().toISOString(), entries: {} };
}

export function hashString(value: string): string {
  return crypto.createHash('sha256').update(value).digest('hex');
}

export function hashFile(filePath: string): string {
  return hashString(fs.readFileSync(filePath, 'utf8'));
}

/** Load the manifest from disk; returns null when missing or corrupt. */
export function loadCache(cachePath: string): BuildCache | null {
  if (!fs.existsSync(cachePath)) return null;
  try {
    const parsed = JSON.parse(fs.readFileSync(cachePath, 'utf8')) as BuildCache;
    if (
      parsed?.version !== CACHE_VERSION ||
      parsed.entries === null ||
      typeof parsed.entries !== 'object'
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveCache(cachePath: string, cache: BuildCache): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(cache, null, 2), 'utf8');
}

/** Drop cache entries for pages that no longer exist in the content dir. */
export function pruneCacheEntries(cache: BuildCache, slugs: string[]): void {
  const keep = new Set(slugs);
  for (const slug of Object.keys(cache.entries)) {
    if (!keep.has(slug)) delete cache.entries[slug];
  }
}

/**
 * Hash of every template artifact that a page depends on: its page template,
 * its layout, and every partial (partials may be pulled in by any template).
 * Any change to one of these forces the page to be rebuilt.
 */
export function templateHashFor(page: Page, templates: TemplateSet): string {
  const parts: string[] = [];
  const template = templates.templates.get(page.template ?? DEFAULT_TEMPLATE);
  if (template) parts.push(template.source);
  const layout = templates.layouts.get(page.layout ?? DEFAULT_LAYOUT);
  if (layout) parts.push(layout.source);
  for (const partial of templates.partials.values()) parts.push(partial.source);
  return hashString(parts.join('\n'));
}

/** Hash of the templates used to render the index page. */
export function indexTemplateHash(templates: TemplateSet): string {
  const parts: string[] = [];
  const index = templates.templates.get('index');
  if (index) parts.push(index.source);
  const layout = templates.layouts.get(DEFAULT_LAYOUT);
  if (layout) parts.push(layout.source);
  for (const partial of templates.partials.values()) parts.push(partial.source);
  return hashString(parts.join('\n'));
}
