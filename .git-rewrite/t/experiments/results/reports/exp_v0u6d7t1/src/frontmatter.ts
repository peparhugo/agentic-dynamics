import matter from "gray-matter";
import fs from "node:fs/promises";
import path from "node:path";
import type { Frontmatter, Page } from "./types.js";

const DEFAULT_FRONTMATTER: Frontmatter = {
  title: "Untitled",
  draft: false,
  tags: [],
};

export function parseFrontmatter(raw: string): {
  data: Frontmatter;
  content: string;
} {
  const parsed = matter(raw);
  const data: Frontmatter = {
    ...DEFAULT_FRONTMATTER,
    ...(parsed.data as Partial<Frontmatter>),
  };
  if (typeof data.tags === "string") {
    data.tags = data.tags.split(",").map((t) => t.trim()).filter(Boolean);
  }
  if (!Array.isArray(data.tags)) {
    data.tags = [];
  }
  return { data, content: parsed.content };
}

export async function discoverMarkdownFiles(sourceDir: string): Promise<string[]> {
  const results: string[] = [];

  async function walk(dir: string): Promise<void> {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.isFile() && entry.name.endsWith(".md")) {
        results.push(fullPath);
      }
    }
  }

  await walk(sourceDir);
  return results.sort();
}

export function sourceToOutputPath(
  sourcePath: string,
  sourceDir: string,
  outputDir: string,
): string {
  const relPath = path.relative(sourceDir, sourcePath);
  const outputRel = relPath.replace(/\.md$/, ".html");
  if (outputRel === "index.html") {
    return path.join(outputDir, "index.html");
  }
  const dirName = outputRel.replace(/\.html$/, "");
  return path.join(outputDir, dirName, "index.html");
}

export function sourceToUrl(
  sourcePath: string,
  sourceDir: string,
): string {
  const relPath = path.relative(sourceDir, sourcePath);
  const urlBase = relPath.replace(/\.md$/, "");
  if (urlBase === "index" || urlBase === "index.html") return "/";
  const name = path.basename(urlBase, path.extname(urlBase));
  const parent = path.dirname(urlBase);
  if (name === "index") return `/${parent}/`;
  return `/${parent}/${name}/`;
}

export function createPage(
  sourcePath: string,
  sourceDir: string,
  outputDir: string,
  raw: string,
): Page {
  const { data, content } = parseFrontmatter(raw);
  return {
    frontmatter: data,
    content,
    html: "",
    sourcePath,
    outputPath: sourceToOutputPath(sourcePath, sourceDir, outputDir),
    url: sourceToUrl(sourcePath, sourceDir),
    tags: data.tags ?? [],
    isDraft: data.draft === true,
  };
}
