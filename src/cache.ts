import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { Frontmatter } from './markdown';

export const CACHE_FILE_NAME = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CacheEntry {
  slug: string;
  sourcePath: string;
  outputPath: string;
  sourceHash: string;
  templatesHash: string;
  title: string;
  date: string | null;
  tags: string[];
  template: string | null;
  layout: string | null;
  frontmatter: Frontmatter;
  html: string;
  buildTimeMs: number;
}

export interface CacheManifest {
  version: number;
  pages: Record<string, CacheEntry>;
}

export function sha256(input: string): string {
  return crypto.createHash('sha256').update(input, 'utf8').digest('hex');
}

export function defaultCacheFile(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE_NAME);
}

export function emptyManifest(): CacheManifest {
  return { version: CACHE_VERSION, pages: {} };
}

export function loadManifest(cacheFile: string): CacheManifest {
  if (!fs.existsSync(cacheFile)) {
    return emptyManifest();
  }
  try {
    const raw = fs.readFileSync(cacheFile, 'utf8');
    const parsed = JSON.parse(raw) as Partial<CacheManifest>;
    if (parsed && typeof parsed.pages === 'object' && parsed.pages !== null) {
      return {
        version: typeof parsed.version === 'number' ? parsed.version : CACHE_VERSION,
        pages: parsed.pages,
      };
    }
    return emptyManifest();
  } catch {
    return emptyManifest();
  }
}

export function saveManifest(cacheFile: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
  fs.writeFileSync(cacheFile, JSON.stringify(manifest, null, 2), 'utf8');
}

function collectFilesRecursive(
  dir: string,
  ext: string,
  out: string[]
): string[] {
  if (!fs.existsSync(dir)) {
    return out;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectFilesRecursive(full, ext, out);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(ext)) {
      out.push(full);
    }
  }
  return out;
}

/**
 * Compute a stable fingerprint for the entire template directory (templates,
 * layouts and partials). Any change to a template file invalidates the
 * fingerprint and therefore the cached pages that depend on it.
 */
export function hashTemplates(templatesDir: string): string {
  const files = collectFilesRecursive(templatesDir, '.hbs', []);
  const lines: string[] = [];
  for (const file of files) {
    const rel = path.relative(templatesDir, file).split(path.sep).join('/');
    const content = fs.readFileSync(file, 'utf8');
    lines.push(`${rel}\n${content}`);
  }
  lines.sort();
  return sha256(lines.join('\n'));
}
