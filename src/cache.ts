import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { CacheManifest, CacheEntry, Frontmatter } from './types';

export function computeHash(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export function computeTemplateHash(templatesDir: string): string {
  const absDir = path.resolve(templatesDir);
  if (!fs.existsSync(absDir)) {
    return '';
  }
  const hashes: string[] = [];
  collectTemplateHashes(absDir, hashes);
  hashes.sort();
  return computeHash(hashes.join(''));
}

function collectTemplateHashes(dir: string, hashes: string[]): void {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectTemplateHashes(fullPath, hashes);
    } else if (entry.isFile() && entry.name.endsWith('.hbs')) {
      const content = fs.readFileSync(fullPath, 'utf-8');
      hashes.push(computeHash(content));
    }
  }
}

export class CacheManager {
  private manifestPath: string;
  private manifest: CacheManifest;

  constructor(manifestPath: string) {
    this.manifestPath = manifestPath;
    this.manifest = { templateHash: '', pages: {} };
  }

  load(): void {
    try {
      if (fs.existsSync(this.manifestPath)) {
        const raw = fs.readFileSync(this.manifestPath, 'utf-8');
        const parsed = JSON.parse(raw);
        if (parsed && parsed.pages) {
          this.manifest = parsed;
        }
      }
    } catch {
      this.manifest = { templateHash: '', pages: {} };
    }
  }

  save(): void {
    const dir = path.dirname(this.manifestPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.manifestPath, JSON.stringify(this.manifest, null, 2), 'utf-8');
  }

  clear(): void {
    this.manifest = { templateHash: '', pages: {} };
    if (fs.existsSync(this.manifestPath)) {
      fs.unlinkSync(this.manifestPath);
    }
  }

  get(filePath: string, contentHash: string, templateHash: string): CacheEntry | null {
    if (this.manifest.templateHash !== templateHash) {
      return null;
    }
    const entry = this.manifest.pages[filePath];
    if (!entry || entry.contentHash !== contentHash || entry.templateHash !== templateHash) {
      return null;
    }
    return entry;
  }

  set(filePath: string, contentHash: string, templateHash: string, html: string): void {
    this.manifest.pages[filePath] = {
      contentHash,
      templateHash,
      html,
    };
  }

  updateTemplateHash(templateHash: string): void {
    this.manifest.templateHash = templateHash;
  }
}
