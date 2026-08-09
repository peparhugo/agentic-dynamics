import { readFileSync } from "node:fs";
import matter from "gray-matter";
import type { Frontmatter, Page } from "./types.js";

export function parseFrontmatter(filePath: string, sourceDir: string): Page | null {
  const raw = readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);

  if (!data.title) return null;

  const frontmatter: Frontmatter = {
    title: String(data.title),
    date: data.date ? String(data.date) : undefined,
    tags: Array.isArray(data.tags)
      ? data.tags.map(String)
      : data.tags
        ? [String(data.tags)]
        : undefined,
    draft: data.draft === true || data.draft === "true",
    layout: data.layout ? String(data.layout) : undefined,
  };

  const rel = filePath.slice(sourceDir.length).replace(/^\//, "");
  const slug = rel.replace(/\.md$/, "").replace(/\\/g, "/");
  const outputPath = slug + "/index.html";

  return {
    sourcePath: filePath,
    outputPath,
    frontmatter,
    markdown: content,
    html: "",
    url: "/" + slug + "/",
  };
}
