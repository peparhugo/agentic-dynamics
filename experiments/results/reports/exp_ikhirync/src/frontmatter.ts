import matter from "gray-matter";
import type { Frontmatter } from "./types.js";

export function parseFrontmatter(raw: string): {
  frontmatter: Frontmatter;
  content: string;
} {
  const { data, content } = matter(raw);
  const fm = data as Frontmatter;

  if (fm.tags !== undefined && !Array.isArray(fm.tags)) {
    fm.tags = [fm.tags as unknown as string];
  }

  if (fm.draft === undefined) {
    fm.draft = false;
  }

  return { frontmatter: fm, content: content.trim() };
}
