import { readFile, writeFile, mkdir, readdir, copyFile, stat } from "node:fs/promises";
import { join, dirname, extname, relative, basename } from "node:path";

export async function readTextFile(path: string): Promise<string> {
  return readFile(path, "utf-8");
}

export async function writeTextFile(path: string, content: string): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, content, "utf-8");
}

export async function ensureDir(dir: string): Promise<void> {
  await mkdir(dir, { recursive: true });
}

export async function* walkDir(dir: string): AsyncGenerator<string> {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkDir(full);
    } else {
      yield full;
    }
  }
}

export async function copyDir(src: string, dest: string): Promise<void> {
  const entries = await readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = join(src, entry.name);
    const destPath = join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDir(srcPath, destPath);
    } else {
      await mkdir(dirname(destPath), { recursive: true });
      await copyFile(srcPath, destPath);
    }
  }
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

export function parseDate(raw: string): Date {
  const d = new Date(raw);
  if (isNaN(d.getTime())) throw new Error(`Invalid date: ${raw}`);
  return d;
}

export function pathToUrl(filePath: string, sourceDir: string): string {
  const rel = relative(sourceDir, filePath);
  const parsed = basename(rel, extname(rel));
  if (parsed === "index") {
    const dirPart = dirname(rel);
    return dirPart === "." ? "/" : `/${dirPart}/`;
  }
  return `/${parsed}/`;
}
