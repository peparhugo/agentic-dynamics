import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { Frontmatter, Page } from "./types";
import { markdownToHtml } from "./syntax";

export function parseFrontmatter(filePath: string): Frontmatter {
  const raw = fs.readFileSync(filePath, "utf-8");
  const parsed = matter(raw);
  const fm = parsed.data as Frontmatter;
  if (!fm.title) {
    throw new Error(`Missing title in frontmatter: ${filePath}`);
  }
  return fm;
}

export function loadMarkdownFile(
  filePath: string,
  relPath: string
): Page {
  const raw = fs.readFileSync(filePath, "utf-8");
  const parsed = matter(raw);
  const fm = parsed.data as Frontmatter;
  if (!fm.title) {
    throw new Error(`Missing title in frontmatter: ${filePath}`);
  }
  const html = markdownToHtml(parsed.content);
  const slug =
    fm.slug ||
    path
      .basename(filePath, ".md")
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");
  fm.tags = (fm.tags || []).map((t) => t.trim().toLowerCase()).filter(Boolean);
  return {
    frontmatter: fm,
    content: parsed.content,
    html,
    slug,
    sourcePath: relPath,
  };
}

export function collectPages(srcDir: string): Page[] {
  const pages: Page[] = [];
  function walk(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.name.endsWith(".md")) {
        const relPath = path.relative(srcDir, fullPath);
        pages.push(loadMarkdownFile(fullPath, relPath));
      }
    }
  }
  walk(srcDir);
  pages.sort((a, b) => {
    const da = a.frontmatter.date ?? "";
    const db = b.frontmatter.date ?? "";
    return db.localeCompare(da);
  });
  return pages;
}
