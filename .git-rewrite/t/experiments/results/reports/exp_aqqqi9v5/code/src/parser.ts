import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import type { Frontmatter, Page } from "./types.js";

function slugify(filePath: string, sourceDir: string): string {
  const rel = path.relative(sourceDir, filePath);
  const parsed = path.parse(rel);
  const slug = path.join(parsed.dir, parsed.name);
  return slug || "index";
}

export function parseFrontmatter(content: string): {
  data: Frontmatter;
  content: string;
} {
  const parsed = matter(content);
  const raw = parsed.data as Record<string, unknown>;

  const data: Frontmatter = {
    title: String(raw.title ?? "Untitled"),
  };

  if (raw.date) {
    if (raw.date instanceof Date) {
      data.date = raw.date.toISOString().slice(0, 10);
    } else {
      data.date = String(raw.date);
    }
  }
  if (raw.tags) {
    if (Array.isArray(raw.tags)) {
      data.tags = raw.tags.map(String);
    } else {
      data.tags = String(raw.tags).split(",").map((s) => s.trim());
    }
  }
  if (raw.draft !== undefined) {
    data.draft = Boolean(raw.draft);
  }

  for (const [key, value] of Object.entries(raw)) {
    if (!["title", "date", "tags", "draft"].includes(key)) {
      data[key] = value;
    }
  }

  return { data, content: parsed.content };
}

export async function parseFile(
  filePath: string,
  sourceDir: string,
  outputDir: string,
): Promise<Page> {
  const raw = await fs.readFile(filePath, "utf-8");
  const { data, content } = parseFrontmatter(raw);
  const slug = slugify(filePath, sourceDir);
  const ext = path.extname(filePath);

  return {
    frontmatter: data,
    content,
    html: "",
    slug,
    sourcePath: filePath,
    outputPath: path.join(outputDir, slug + ".html"),
    isDraft: data.draft === true,
  };
}
