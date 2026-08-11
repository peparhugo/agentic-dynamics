import { promises as fs } from "fs";
import path from "path";
import crypto from "crypto";
import { Frontmatter } from "./types";

export interface CacheEntry {
  sourceHash: string;
  templatesHash: string;
  frontmatter: Frontmatter;
  html: string;
}

export interface CacheManifest {
  version: number;
  templatesHash: string;
  entries: Record<string, CacheEntry>;
}

export function hashContent(content: string): string {
  return crypto.createHash("sha256").update(content).digest("hex").slice(0, 16);
}

export async function hashDirectory(dir: string): Promise<string> {
  const hash = crypto.createHash("sha256");
  try {
    const files = await walkFiles(dir);
    const sorted = files.sort();
    for (const f of sorted) {
      const content = await fs.readFile(f, "utf-8");
      hash.update(f);
      hash.update(content);
    }
  } catch {
  }
  return hash.digest("hex").slice(0, 16);
}

async function walkFiles(dir: string): Promise<string[]> {
  const results: string[] = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return results;
  }
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      const sub = await walkFiles(fullPath);
      results.push(...sub);
    } else {
      results.push(fullPath);
    }
  }
  return results;
}

export class BuildCache {
  private manifest: CacheManifest;
  private cachePath: string;

  constructor(outputDir: string) {
    this.cachePath = path.join(outputDir, ".ssg-cache.json");
    this.manifest = { version: 1, templatesHash: "", entries: {} };
  }

  async load(): Promise<void> {
    try {
      const raw = await fs.readFile(this.cachePath, "utf-8");
      const parsed = JSON.parse(raw);
      if (parsed && parsed.version === 1) {
        this.manifest = parsed;
      }
    } catch {
      this.manifest = { version: 1, templatesHash: "", entries: {} };
    }
  }

  async save(): Promise<void> {
    await fs.writeFile(this.cachePath, JSON.stringify(this.manifest, null, 2), "utf-8");
  }

  getEntry(filePath: string): CacheEntry | undefined {
    return this.manifest.entries[filePath];
  }

  setEntry(filePath: string, entry: CacheEntry): void {
    this.manifest.entries[filePath] = entry;
  }

  isChanged(filePath: string, sourceHash: string, templatesHash: string): boolean {
    const entry = this.manifest.entries[filePath];
    if (!entry) return true;
    return entry.sourceHash !== sourceHash || entry.templatesHash !== templatesHash;
  }

  getTemplatesHash(): string {
    return this.manifest.templatesHash;
  }

  setTemplatesHash(hash: string): void {
    this.manifest.templatesHash = hash;
  }

  clear(): void {
    this.manifest = { version: 1, templatesHash: "", entries: {} };
  }
}
