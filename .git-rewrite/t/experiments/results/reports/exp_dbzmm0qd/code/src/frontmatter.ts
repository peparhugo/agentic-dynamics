import matter from "gray-matter";
import { Frontmatter } from "./types.js";

export function parseFrontmatter(markdown: string): {
  frontmatter: Frontmatter;
  content: string;
} {
  const { data, content } = matter(markdown);

  const frontmatter: Frontmatter = {
    title: data.title ?? "Untitled",
  };

  if (data.date) {
    const d = new Date(data.date);
    if (!isNaN(d.getTime())) frontmatter.date = d;
  }

  if (data.tags) {
    frontmatter.tags = Array.isArray(data.tags)
      ? data.tags.map((t: unknown) => String(t))
      : String(data.tags)
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
  }

  if (data.draft !== undefined) {
    frontmatter.draft = Boolean(data.draft);
  }

  if (typeof data.layout === "string") {
    frontmatter.layout = data.layout;
  }

  return { frontmatter, content };
}
