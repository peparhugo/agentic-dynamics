import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";
import type { Frontmatter, Post } from "./types.js";

marked.use(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code: string, lang: string) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
  })
);

export function parseFrontmatter(raw: string): { frontmatter: Frontmatter; content: string } {
  const parsed = matter(raw);
  const fm = parsed.data as Frontmatter;
  if (!fm.title) {
    throw new Error("Frontmatter must include a title");
  }
  if (fm.tags && typeof fm.tags === "string") {
    fm.tags = (fm.tags as string).split(",").map((t) => t.trim());
  }
  fm.tags = fm.tags ?? [];
  fm.draft = fm.draft ?? false;
  return { frontmatter: fm, content: parsed.content };
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export async function loadPosts(sourceDir: string, includeDrafts: boolean): Promise<Post[]> {
  const entries = await fs.readdir(sourceDir, { withFileTypes: true });
  const mdFiles = entries.filter((e) => e.isFile() && e.name.endsWith(".md"));

  const posts: Post[] = [];
  for (const file of mdFiles) {
    const raw = await fs.readFile(path.join(sourceDir, file.name), "utf-8");
    const { frontmatter, content } = parseFrontmatter(raw);
    if (frontmatter.draft && !includeDrafts) continue;
    const html = await marked.parse(content);
    const slug = slugify(frontmatter.title);
    const excerpt = extractExcerpt(html);
    posts.push({ slug, frontmatter, content, html, excerpt });
  }

  posts.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  return posts;
}

export function buildTagIndex(posts: Post[]): Record<string, Post[]> {
  const tags: Record<string, Post[]> = {};
  for (const post of posts) {
    for (const tag of post.frontmatter.tags ?? []) {
      if (!tags[tag]) tags[tag] = [];
      tags[tag].push(post);
    }
  }
  return tags;
}

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toISOString().split("T")[0];
}

function extractExcerpt(html: string): string {
  const text = html.replace(/<[^>]+>/g, "");
  return text.length > 200 ? text.slice(0, 200) + "..." : text;
}
