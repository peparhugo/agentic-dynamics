import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { Frontmatter, Page } from "./types";

function normalizeDate(d: unknown): string | undefined {
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  if (typeof d === "string") return d;
  return undefined;
}

export function parseFrontmatter(filePath: string): { frontmatter: Frontmatter; content: string } {
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);
  const fm = data as Frontmatter;
  fm.date = normalizeDate(fm.date);
  return {
    frontmatter: fm,
    content: content.trim(),
  };
}

export function slugFromPath(filePath: string, sourceDir: string): string {
  const rel = path.relative(sourceDir, filePath);
  const ext = path.extname(rel);
  let slug = rel.slice(0, -ext.length);
  if (slug.endsWith("/index") || slug === "index") {
    slug = path.dirname(slug) || ".";
  }
  if (slug === ".") slug = "";
  return slug;
}

export function isValidPage(fm: Frontmatter): boolean {
  return !!fm.title && !fm.draft;
}

export async function collectPages(sourceDir: string): Promise<Page[]> {
  const pages: Page[] = [];

  function walk(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith(".md") || entry.name.endsWith(".mdx"))) {
        const { frontmatter, content } = parseFrontmatter(fullPath);
        const slug = slugFromPath(fullPath, sourceDir);
        pages.push({
          frontmatter,
          content,
          html: "",
          slug,
          sourcePath: fullPath,
        });
      }
    }
  }

  walk(sourceDir);
  return pages;
}
