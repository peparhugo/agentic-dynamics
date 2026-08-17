import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { BuildOptions, Frontmatter } from './types';
import {
  resolveTemplateFile,
  resolveLayoutFile,
  listPartialFiles,
  DEFAULT_TEMPLATE_NAME,
  DEFAULT_LAYOUT_NAME,
  DEFAULT_TEMPLATE_SOURCE,
  DEFAULT_LAYOUT_SOURCE,
} from './templates';

export const CACHE_VERSION = 1;
export const CACHE_FILENAME = '.ssg-cache.json';

/**
 * A single page's cached build fingerprint. `sourceHash` covers the markdown
 * source, `templateHash` covers the template/layout/partials that affect the
 * page's rendered output, and the remaining fields let us reconstruct the page
 * (and skip re-parsing/re-rendering) on subsequent incremental builds.
 */
export interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  frontmatter: Frontmatter;
  template?: string;
  layout?: string | false;
}

export interface CacheManifest {
  version: number;
  pages: Record<string, CacheEntry>;
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export function hashFile(file: string): string | null {
  try {
    return hashContent(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

export function defaultManifest(): CacheManifest {
  return { version: CACHE_VERSION, pages: {} };
}

export function loadManifest(file: string): CacheManifest {
  try {
    if (!fs.existsSync(file)) {
      return defaultManifest();
    }
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (
      parsed &&
      parsed.version === CACHE_VERSION &&
      parsed.pages &&
      typeof parsed.pages === 'object' &&
      !Array.isArray(parsed.pages)
    ) {
      return parsed as CacheManifest;
    }
  } catch {
    // Fall through to a fresh manifest on any parse error.
  }
  return defaultManifest();
}

export function saveManifest(file: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(manifest, null, 2));
}

/**
 * Compute the template fingerprint for a page: the resolved template and
 * layout sources (or their built-in defaults) plus every registered partial.
 * Any change to one of these files changes the fingerprint and invalidates the
 * page's cache entry.
 */
export function computeTemplateHash(
  options: BuildOptions,
  templateName?: string,
  layoutName?: string | false
): string {
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const layoutsDir = path.join(templatesDir, 'layouts');
  const partialsDir = path.join(templatesDir, 'partials');

  const defaultTemplate = options.defaultTemplate ?? DEFAULT_TEMPLATE_NAME;
  const defaultLayout = options.defaultLayout ?? DEFAULT_LAYOUT_NAME;

  const templateFile = resolveTemplateFile(templatesDir, templateName, defaultTemplate);
  const layoutFile =
    layoutName === false ? null : resolveLayoutFile(layoutsDir, layoutName, defaultLayout);

  const parts: string[] = [];
  parts.push(templateFile ? (hashFile(templateFile) ?? '') : DEFAULT_TEMPLATE_SOURCE);
  parts.push(layoutName === false ? '' : layoutFile ? (hashFile(layoutFile) ?? '') : DEFAULT_LAYOUT_SOURCE);

  for (const partialFile of listPartialFiles(partialsDir)) {
    parts.push(`${partialFile}:${hashFile(partialFile) ?? ''}`);
  }

  return hashContent(parts.join('\n'));
}
