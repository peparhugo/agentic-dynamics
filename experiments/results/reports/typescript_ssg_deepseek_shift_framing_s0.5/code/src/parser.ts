import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { Page, Frontmatter } from "./types";

export function parseFrontmatter(filePath: string): { frontmatter: Frontmatter; content: string } {
  const raw = fs.readFileSync(filePath, "utf-8");
  const parsed = matter(raw);
  return { frontmatter: parsed.data as Frontmatter, content: parsed.content };
}

export function collectMarkdownFiles(sourceDir: string): string[] {
  const files: string[] = [];
  function walk(dir: string) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith(".md")) {
        files.push(full);
      }
    }
  }
  walk(sourceDir);
  return files;
}

export function deriveUrlPath(filePath: string, sourceDir: string): string {
  const rel = path.relative(sourceDir, filePath);
  const parsed = path.parse(rel);
  const dir = parsed.dir || ".";
  const name = parsed.name === "index" ? "" : parsed.name;
  if (dir === "." && !name) return "/";
  const joined = path.join(dir, name);
  return "/" + joined.replace(/\\/g, "/") + "/";
}
