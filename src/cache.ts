import fs from 'fs/promises';
import path from 'path';
import { Page } from './types';

export const CACHE_FILE = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CachedPage {
  hash: string;
  templateHash: string;
  buildMs: number;
  page: Page;
}

export interface CacheManifest {
  version: number;
  generatedAt: string;
  pages: Record<string, CachedPage>;
}

export interface BuildStats {
  built: number;
  skipped: number;
  total: number;
  timeSavedMs: number;
  totalMs: number;
}

export function cacheFilePath(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE);
}

export async function loadCache(outputDir: string): Promise<CacheManifest | undefined> {
  try {
    const raw = await fs.readFile(cacheFilePath(outputDir), 'utf-8');
    const manifest = JSON.parse(raw) as CacheManifest;
    if (!manifest || manifest.version !== CACHE_VERSION) return undefined;
    return manifest;
  } catch {
    return undefined;
  }
}

export async function saveCache(
  outputDir: string,
  manifest: CacheManifest
): Promise<void> {
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(
    cacheFilePath(outputDir),
    JSON.stringify(manifest, null, 2),
    'utf-8'
  );
}
