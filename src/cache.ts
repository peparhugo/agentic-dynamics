import { createHash } from 'crypto';
import { promises as fs } from 'fs';
import path from 'path';
import { BUILTIN_TEMPLATE_SOURCE } from './engine';
import type { Page } from './types';

export const MANIFEST_VERSION = 1;

export interface CachedPage {
  slug: string;
  page: Page;
  rendered: string;
  sourceHash: string;
  templateHash: string;
}

export interface CacheManifest {
  version: number;
  templateHash: string;
  avgMsPerPage: number;
  pages: Record<string, CachedPage>;
}

export function hashString(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

async function collectFiles(dir: string, ext: string, out: string[]): Promise<void> {
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await collectFiles(full, ext, out);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(ext)) {
      out.push(full);
    }
  }
}

export async function computeTemplatesHash(templatesDir: string): Promise<string> {
  const files: string[] = [];
  await collectFiles(templatesDir, '.hbs', files);
  files.sort();
  const parts = [hashString(BUILTIN_TEMPLATE_SOURCE)];
  for (const file of files) {
    const content = await fs.readFile(file, 'utf8');
    parts.push(hashString(content));
  }
  return hashString(parts.join('\n'));
}

export async function loadManifest(cacheFile: string): Promise<CacheManifest | null> {
  try {
    const raw = await fs.readFile(cacheFile, 'utf8');
    const parsed = JSON.parse(raw) as CacheManifest;
    if (
      parsed &&
      typeof parsed === 'object' &&
      parsed.version === MANIFEST_VERSION &&
      parsed.pages &&
      typeof parsed.pages === 'object'
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export async function saveManifest(cacheFile: string, manifest: CacheManifest): Promise<void> {
  await fs.mkdir(path.dirname(cacheFile), { recursive: true });
  await fs.writeFile(cacheFile, JSON.stringify(manifest, null, 2), 'utf8');
}
