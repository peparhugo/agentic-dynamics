import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";

export interface Frontmatter {
  title: string;
  date: Date;
  tags: string[];
  draft: boolean;
  layout: string;
  [key: string]: unknown;
}

export interface Post extends Frontmatter {
  /** Slug derived from the file path relative to the source dir, e.g. "posts/hello". */
  slug: string;
  /** Site-relative URL, e.g. "/posts/hello/". */
  url: string;
  /** Rendered HTML body. */
  html: string;
  /** Raw markdown body. */
  raw: string;
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export const md: MarkdownIt = new MarkdownIt({
  html: true,
  linkify: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      const { value } = hljs.highlight(code, { language: lang, ignoreIllegals: true });
      return `<pre><code class="hljs language-${lang}">${value}</code></pre>`;
    }
    return `<pre><code class="hljs">${escapeHtml(code)}</code></pre>`;
  },
});

/** Normalize raw frontmatter data into a well-typed Frontmatter object. */
export function normalizeFrontmatter(data: Record<string, unknown>, fallbackTitle: string): Frontmatter {
  const title = typeof data.title === "string" && data.title.trim() !== "" ? data.title : fallbackTitle;

  let date: Date;
  if (data.date instanceof Date) date = data.date;
  else if (typeof data.date === "string" || typeof data.date === "number") {
    const parsed = new Date(data.date);
    date = Number.isNaN(parsed.getTime()) ? new Date(0) : parsed;
  } else date = new Date(0);

  let tags: string[];
  if (Array.isArray(data.tags)) tags = data.tags.map(String).filter((t) => t.trim() !== "");
  else if (typeof data.tags === "string") tags = data.tags.split(",").map((t) => t.trim()).filter(Boolean);
  else tags = [];

  const draft = data.draft === true;
  const layout = typeof data.layout === "string" && data.layout.trim() !== "" ? data.layout : "post";

  return { ...data, title, date, tags, draft, layout };
}

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9/]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
}

/** Parse a single markdown document (frontmatter + body) into a Post. */
export function parsePost(rawFile: string, relPath: string): Post {
  const { data, content } = matter(rawFile);
  const noExt = relPath.replace(/\\/g, "/").replace(/\.(md|markdown)$/i, "");
  const slug = noExt.split("/").map(slugify).join("/");
  const fallbackTitle = path.basename(noExt);
  const fm = normalizeFrontmatter(data, fallbackTitle);
  return {
    ...fm,
    slug,
    url: `/${slug}/`,
    html: md.render(content),
    raw: content,
  };
}

async function walk(dir: string, base: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const out: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full, base)));
    else out.push(path.relative(base, full));
  }
  return out;
}

export interface LoadResult {
  posts: Post[];
  /** Relative paths of non-markdown files to copy through verbatim. */
  assets: string[];
}

/** Load all markdown files under sourceDir. Posts are sorted newest first. */
export async function loadContent(sourceDir: string, includeDrafts = false): Promise<LoadResult> {
  const files = await walk(sourceDir, sourceDir);
  const posts: Post[] = [];
  const assets: string[] = [];
  for (const rel of files) {
    if (/\.(md|markdown)$/i.test(rel)) {
      const raw = await fs.readFile(path.join(sourceDir, rel), "utf8");
      const post = parsePost(raw, rel);
      if (post.draft && !includeDrafts) continue;
      posts.push(post);
    } else {
      assets.push(rel);
    }
  }
  posts.sort((a, b) => b.date.getTime() - a.date.getTime());
  return { posts, assets };
}
