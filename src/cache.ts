import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { Frontmatter, Page, parseFrontmatter } from './ssg';

export const CACHE_FILE_NAME = '.ssg-cache.json';

/** A single cached page: its post-plugin metadata plus the final rendered HTML. */
export interface CachedPage {
  page: Page;
  outputHtml: string;
}

export interface CacheManifest {
  version: number;
  /** Map of content-relative source path -> sha256 hash of the raw file. */
  files: Record<string, string>;
  /** Combined hash of every template file under the templates directory. */
  templatesHash: string;
  /** Map of slug -> cached rendered page. */
  pages: Record<string, CachedPage>;
}

export function hashString(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

export function hashFileContents(filePath: string): string {
  return hashString(fs.readFileSync(filePath, 'utf8'));
}

/** Recursively collect all files under a directory, sorted by path. */
export function collectFiles(dir: string): string[] {
  const results: string[] = [];

  function walk(current: string): void {
    if (!fs.existsSync(current)) {
      return;
    }
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        results.push(full);
      }
    }
  }

  walk(dir);
  return results.sort();
}

/**
 * Compute a combined hash over the relative paths and contents of every file
 * under a directory. Used to detect changes to templates/partials/layouts.
 */
export function hashDirectoryContents(dir: string): string {
  const files = collectFiles(dir);
  const hasher = crypto.createHash('sha256');
  for (const file of files) {
    hasher.update(path.relative(dir, file));
    hasher.update('\0');
    hasher.update(fs.readFileSync(file, 'utf8'));
    hasher.update('\0');
  }
  return hasher.digest('hex');
}

export function createEmptyManifest(): CacheManifest {
  return { version: 1, files: {}, templatesHash: '', pages: {} };
}

export function loadManifest(cachePath: string): CacheManifest {
  try {
    const raw = fs.readFileSync(cachePath, 'utf8');
    const parsed = JSON.parse(raw) as Partial<CacheManifest>;
    if (
      parsed &&
      parsed.version === 1 &&
      typeof parsed.files === 'object' &&
      parsed.files !== null &&
      typeof parsed.pages === 'object' &&
      parsed.pages !== null &&
      typeof parsed.templatesHash === 'string'
    ) {
      return parsed as CacheManifest;
    }
    return createEmptyManifest();
  } catch {
    return createEmptyManifest();
  }
}

export function saveManifest(cachePath: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(manifest, null, 2), 'utf8');
}

interface ParsedResult {
  frontmatter: Frontmatter;
  content: string;
}

/** In-memory cache of parsed frontmatter, keyed by the raw source hash. */
const frontmatterCache = new Map<string, ParsedResult>();

export function parseFrontmatterCached(raw: string): ParsedResult {
  const key = hashString(raw);
  const cached = frontmatterCache.get(key);
  if (cached) {
    return cached;
  }
  const result = parseFrontmatter(raw);
  frontmatterCache.set(key, result);
  return result;
}
