import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

export interface CacheEntry {
  sourceHash: string;
  templatesHash: string;
  outputHtml: string;
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface SsgCacheManifest {
  version: number;
  pages: Record<string, CacheEntry>;
  templatesHash: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export function hashFile(filePath: string): string {
  if (!fs.existsSync(filePath)) return '';
  return hashContent(fs.readFileSync(filePath, 'utf-8'));
}

export function computeTemplatesHash(templatesDir: string): string {
  if (!templatesDir || !fs.existsSync(templatesDir)) return '';
  const hashes: string[] = [];
  const walkDir = (dir: string): void => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walkDir(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith('.hbs') || entry.name.endsWith('.html'))) {
        hashes.push(hashFile(fullPath));
      }
    }
  };
  walkDir(templatesDir);
  return hashContent(hashes.sort().join(''));
}

export function loadCache(cachePath: string): SsgCacheManifest | null {
  if (!fs.existsSync(cachePath)) return null;
  try {
    const data = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
    if (data && data.version === 1 && typeof data.pages === 'object') {
      return data as SsgCacheManifest;
    }
    return null;
  } catch {
    return null;
  }
}

export function saveCache(cachePath: string, manifest: SsgCacheManifest): void {
  const dir = path.dirname(cachePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(cachePath, JSON.stringify(manifest, null, 2));
}

export function removeCache(cachePath: string): void {
  if (fs.existsSync(cachePath)) {
    fs.unlinkSync(cachePath);
  }
}

export function createEmptyManifest(): SsgCacheManifest {
  return { version: 1, pages: {}, templatesHash: '' };
}
