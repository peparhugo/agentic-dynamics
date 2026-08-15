import { promises as fs } from 'fs';
import path from 'path';
import crypto from 'crypto';
import type { Frontmatter } from './frontmatter';

export interface CachedPage {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  contentHtml: string;
  sourcePath: string;
  outputPath: string;
  template?: string;
  layout?: string;
  data: Frontmatter;
  content?: string;
  html?: string;
  sourceHash: string;
  templateHash: string;
  buildTimeMs: number;
}

export interface CacheManifest {
  version: number;
  templatesHash: string;
  pages: Record<string, CachedPage>;
}

export const CACHE_VERSION = 1;
export const CACHE_FILENAME = '.ssg-cache.json';

export function hashString(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

export async function hashFile(filePath: string): Promise<string> {
  try {
    const content = await fs.readFile(filePath);
    return hashString(content.toString('utf8'));
  } catch {
    return '';
  }
}

const TEMPLATE_EXTS = new Set(['.hbs', '.handlebars', '.html']);

async function collectTemplateFiles(
  root: string,
  dir: string,
  out: Array<{ rel: string; hash: string }>
): Promise<void> {
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await collectTemplateFiles(root, full, out);
    } else if (
      entry.isFile() &&
      TEMPLATE_EXTS.has(path.extname(entry.name).toLowerCase())
    ) {
      const hash = await hashFile(full);
      out.push({ rel: path.relative(root, full), hash });
    }
  }
}

export async function computeTemplatesHash(templatesDir: string): Promise<string> {
  const root = path.resolve(templatesDir);
  const files: Array<{ rel: string; hash: string }> = [];
  await collectTemplateFiles(root, root, files);
  files.sort((a, b) => a.rel.localeCompare(b.rel));
  return hashString(files.map((f) => `${f.rel}:${f.hash}`).join('\n'));
}

export class CacheManager {
  private readonly cachePath: string;

  constructor(outputDir: string) {
    this.cachePath = path.join(path.resolve(outputDir), CACHE_FILENAME);
  }

  async load(): Promise<CacheManifest | undefined> {
    try {
      const raw = await fs.readFile(this.cachePath, 'utf8');
      const parsed = JSON.parse(raw) as CacheManifest;
      if (!parsed || parsed.version !== CACHE_VERSION || !parsed.pages) {
        return undefined;
      }
      return parsed;
    } catch {
      return undefined;
    }
  }

  async save(manifest: CacheManifest): Promise<void> {
    await fs.mkdir(path.dirname(this.cachePath), { recursive: true });
    await fs.writeFile(this.cachePath, JSON.stringify(manifest, null, 2), 'utf8');
  }

  async clear(): Promise<void> {
    try {
      await fs.rm(this.cachePath, { force: true });
    } catch {
      // ignore
    }
  }
}
