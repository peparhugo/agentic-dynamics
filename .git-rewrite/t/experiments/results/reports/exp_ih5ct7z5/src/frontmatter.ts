import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { Frontmatter, Post } from "./types";

export function parseFrontmatter(filePath: string): { frontmatter: Frontmatter; content: string } {
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);

  const fm: Frontmatter = {
    title: data.title || path.basename(filePath, ".md"),
    date: data.date || undefined,
    tags: normalizeTags(data.tags),
    draft: data.draft === true || data.draft === "true",
    ...(data as Record<string, unknown>),
  };

  return { frontmatter: fm, content };
}

function normalizeTags(tags: unknown): string[] {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags.map(String).filter(Boolean);
  if (typeof tags === "string") return tags.split(",").map((t) => t.trim()).filter(Boolean);
  return [];
}

export function loadPosts(sourceDir: string, includeDrafts = false): Post[] {
  const entries = fs.readdirSync(sourceDir, { withFileTypes: true });
  const posts: Post[] = [];

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;

    const filePath = path.join(sourceDir, entry.name);
    const { frontmatter, content } = parseFrontmatter(filePath);
    if (frontmatter.draft && !includeDrafts) continue;

    const slug = entry.name.replace(/\.md$/, "");
    posts.push({
      slug,
      frontmatter,
      content,
      html: "",
      url: frontmatter.draft ? `/${slug}.html` : `/${slug}.html`,
    });
  }

  posts.sort((a, b) => {
    const dateA = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const dateB = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return dateB - dateA;
  });

  return posts;
}
