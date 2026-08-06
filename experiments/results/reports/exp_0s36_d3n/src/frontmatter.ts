import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { Frontmatter, Page } from "./types";

export function parseFrontmatter(filePath: string): {
  frontmatter: Frontmatter;
  content: string;
} {
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);
  const fm = data as Frontmatter;

  if (fm.draft === undefined) {
    fm.draft = false;
  }

  return { frontmatter: fm, content };
}

export function resolvePages(sourceDir: string, basePath: string = ""): Page[] {
  const pages: Page[] = [];
  const entries = fs.readdirSync(sourceDir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(sourceDir, entry.name);
    if (entry.isDirectory()) {
      pages.push(...resolvePages(fullPath, path.join(basePath, entry.name)));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      pages.push(processMarkdownFile(fullPath, basePath, sourceDir));
    }
  }

  return pages;
}

function processMarkdownFile(
  filePath: string,
  basePath: string,
  sourceDir: string
): Page {
  const { frontmatter, content } = parseFrontmatter(filePath);
  const relativePath = filePath.replace(sourceDir + path.sep, "");
  const slug = relativePath.replace(/\.md$/, "").replace(/\\/g, "/");
  const fileName = path.basename(filePath, ".md");
  const dir = basePath ? basePath.replace(/\\/g, "/") : "";

  let url: string;
  if (fileName === "index") {
    url = dir ? `/${dir}/` : "/";
  } else {
    url = dir ? `/${dir}/${fileName}/` : `/${fileName}/`;
  }

  return {
    path: filePath,
    relativePath,
    frontmatter,
    content,
    html: "",
    url,
  };
}

export function getPublishedPages(pages: Page[]): Page[] {
  return pages.filter((p) => !p.frontmatter.draft);
}

export function getSortedPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const dateA = a.frontmatter.date
      ? new Date(a.frontmatter.date).getTime()
      : 0;
    const dateB = b.frontmatter.date
      ? new Date(b.frontmatter.date).getTime()
      : 0;
    return dateB - dateA;
  });
}

export function getTags(pages: Page[]): Map<string, Page[]> {
  const tagMap = new Map<string, Page[]>();
  for (const page of pages) {
    const tags = page.frontmatter.tags;
    if (tags) {
      for (const tag of tags) {
        const existing = tagMap.get(tag) || [];
        existing.push(page);
        tagMap.set(tag, existing);
      }
    }
  }
  return tagMap;
}
