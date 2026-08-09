import matter from "gray-matter";
import { Frontmatter } from "./types.js";

export function parseFrontmatter(raw: string): {
  frontmatter: Frontmatter;
  content: string;
} {
  const parsed = matter(raw);
  const fm = parsed.data as Frontmatter;

  if (fm.date && typeof fm.date === "string") {
    fm.date = new Date(fm.date);
  }
  if (typeof fm.tags === "string") {
    fm.tags = fm.tags.split(",").map((t) => t.trim()).filter(Boolean);
  }
  if (!fm.tags) {
    fm.tags = [];
  }
  if (typeof fm.draft !== "boolean") {
    fm.draft = fm.draft === "true" || fm.draft === true;
  }

  return { frontmatter: fm, content: parsed.content };
}
