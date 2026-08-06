import matter from "gray-matter";
import { Frontmatter, Page } from "./types";

export function parseFrontmatter(raw: string, filePath: string): { frontmatter: Frontmatter; content: string } {
  const parsed = matter(raw);
  const fm = parsed.data as Frontmatter;

  if (fm.date && typeof fm.date === "string") {
    fm.date = new Date(fm.date);
  }

  if (fm.tags && typeof fm.tags === "string") {
    fm.tags = (fm.tags as string).split(",").map((t) => t.trim());
  }

  if (!fm.tags) {
    fm.tags = [];
  }

  return {
    frontmatter: fm,
    content: parsed.content,
  };
}

export function isPublished(page: Pick<Frontmatter, "draft">): boolean {
  return !page.draft;
}

export function pageUrl(filePath: string): string {
  let url = filePath.replace(/\.md$/, ".html");
  if (url.endsWith("index.html") && url !== "index.html") {
    url = url.replace(/index\.html$/, "");
  }
  if (!url.startsWith("/")) {
    url = "/" + url;
  }
  return url;
}

export function sortByDate(a: Page, b: Page): number {
  const da = a.frontmatter.date?.getTime() ?? 0;
  const db = b.frontmatter.date?.getTime() ?? 0;
  return db - da;
}
