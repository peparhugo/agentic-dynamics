import * as fs from 'fs';
import * as path from 'path';
import { createHash } from 'crypto';
import type { Frontmatter } from './types';
import { findTemplateFile } from './template-engine';
import type { SiteConfig } from './template';

export const CACHE_FILE_NAME = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CachePageEntry {
  sourceHash: string;
  templates: Record<string, string>;
  data: Frontmatter;
  content: string;
  html: string;
  buildMs: number;
}

export interface BuildCache {
  version: number;
  contentDir: string;
  outputDir: string;
  siteTitle: string;
  templatesDir: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  pages: Record<string, CachePageEntry>;
}

const TEMPLATE_FILE_EXTENSION = /\.(hbs|ejs|html)$/i;

export function hashSource(source: string): string {
  return createHash('sha256').update(source, 'utf8').digest('hex');
}

export function hashFile(filePath: string): string {
  try {
    return hashSource(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return '';
  }
}

export function cacheFilePath(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE_NAME);
}

export function readCache(outputDir: string): BuildCache | null {
  try {
    const raw = fs.readFileSync(cacheFilePath(outputDir), 'utf8');
    const parsed: unknown = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== 'object' ||
      (parsed as BuildCache).version !== CACHE_VERSION ||
      typeof (parsed as BuildCache).pages !== 'object'
    ) {
      return null;
    }
    return parsed as BuildCache;
  } catch {
    return null;
  }
}

export function writeCache(outputDir: string, cache: BuildCache): void {
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(cacheFilePath(outputDir), JSON.stringify(cache, null, 2), 'utf8');
}

export function deleteCache(outputDir: string): void {
  try {
    fs.rmSync(cacheFilePath(outputDir), { force: true });
  } catch {
    // ignore
  }
}

function listFiles(dir: string): string[] {
  const files: string[] = [];
  const walk = (current: string): void => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        files.push(full);
      }
    }
  };
  walk(dir);
  return files.sort();
}

/**
 * Resolves the set of template files a page depends on and hashes each one.
 * Includes the named template, the layout, and every partial (which may be
 * referenced by any template or layout).
 */
export function collectTemplateDependencies(
  siteConfig: SiteConfig,
  page: { template?: string; layout?: string }
): Record<string, string> {
  const deps: Record<string, string> = {};
  const templatesDir = siteConfig.templatesDir;
  if (!templatesDir || !fs.existsSync(templatesDir)) return deps;

  const templateName = page.template ?? siteConfig.defaultTemplate ?? 'default';
  const layoutName = page.layout ?? siteConfig.defaultLayout ?? 'default';

  const templateFile = findTemplateFile(templatesDir, templateName);
  if (templateFile) deps[templateFile] = hashFile(templateFile);

  const layoutsDir = path.join(templatesDir, 'layouts');
  const layoutFile = findTemplateFile(layoutsDir, layoutName);
  if (layoutFile) deps[layoutFile] = hashFile(layoutFile);

  const partialsDir = path.join(templatesDir, 'partials');
  if (fs.existsSync(partialsDir)) {
    for (const file of listFiles(partialsDir)) {
      if (TEMPLATE_FILE_EXTENSION.test(file)) {
        deps[file] = hashFile(file);
      }
    }
  }

  return deps;
}

export function templatesUnchanged(
  cached: Record<string, string>,
  siteConfig: SiteConfig,
  page: { template?: string; layout?: string }
): boolean {
  const current = collectTemplateDependencies(siteConfig, page);
  const cachedKeys = Object.keys(cached).sort();
  const currentKeys = Object.keys(current).sort();
  if (cachedKeys.length !== currentKeys.length) return false;
  for (const key of cachedKeys) {
    if (cached[key] !== current[key]) return false;
  }
  return true;
}

export function cacheMatches(cache: BuildCache, context: {
  contentDir: string;
  outputDir: string;
  siteConfig: SiteConfig;
}): boolean {
  return (
    cache.contentDir === context.contentDir &&
    cache.outputDir === context.outputDir &&
    cache.siteTitle === context.siteConfig.title &&
    cache.templatesDir === (context.siteConfig.templatesDir ?? '') &&
    cache.defaultTemplate === context.siteConfig.defaultTemplate &&
    cache.defaultLayout === context.siteConfig.defaultLayout
  );
}
