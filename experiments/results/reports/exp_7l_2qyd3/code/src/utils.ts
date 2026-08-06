import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const decoder = new TextDecoder();

export function readTextFile(fpath: string): string {
  return fs.readFileSync(fpath, "utf-8");
}

export function writeTextFile(fpath: string, data: string): void {
  fs.mkdirSync(path.dirname(fpath), { recursive: true });
  fs.writeFileSync(fpath, data, "utf-8");
}

export function copyFile(src: string, dest: string): void {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

export function walkDir(
  dir: string,
  cb: (fpath: string, relative: string) => void
): void {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkDir(full, cb);
    } else if (entry.isFile()) {
      cb(full, path.relative(dir, full));
    }
  }
}

export function normalizeMarkdownPath(relative: string): string {
  const parsed = path.parse(relative);
  if (parsed.name === "index") {
    return path.join(parsed.dir, "index.html");
  }
  return path.join(parsed.dir, parsed.name, "index.html");
}

export function inDevMode(params: URLSearchParams): boolean {
  return params.has("devmode");
}
