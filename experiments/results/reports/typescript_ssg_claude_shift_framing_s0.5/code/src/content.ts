import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { Marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";
import type { Frontmatter, Page } from "./types.js";

const marked = new Marked(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code, lang) {
      const language = hljs.getLanguage(lang) ? lang : "plaintext";
      return hljs.highlight(code, { language }).value;
    },
  }),
);

/** Parse YAML frontmatter + markdown body from raw file contents. */
export function parseFrontmatter(raw: string): { frontmatter: Frontmatter; body: string } {
  const { data, content } = matter(raw);

  let date: Date | null = null;
  if (data.date instanceof Date) date = data.date;
  else if (typeof data.date === "string" || typeof data.date === "number") {
    const d = new Date(data.date);
    if (!Number.isNaN(d.getTime())) date = d;
  }

  let tags: string[] = [];
  if (Array.isArray(data.tags)) tags = data.tags.map(String);
  else if (typeof data.tags === "string") {
    tags = data.tags.split(",").map((t: string) => t.trim()).filter(Boolean);
  }

  const frontmatter: Frontmatter = {
    ...data,
    title: typeof data.title === "string" ? data.title : "",
    date,
    tags,
    draft: data.draft === true,
    layout: typeof data.layout === "string" ? data.layout : undefined,
  };
  return { frontmatter, body: content };
}

/** Render markdown to HTML with syntax-highlighted code blocks. */
export function renderMarkdown(body: string): string {
  return marked.parse(body, { async: false }) as string;
}

/** Derive URL + output path from a source-relative markdown path (pretty URLs). */
export function pathsFor(relPath: string): { url: string; outputPath: string } {
  const posix = relPath.split(path.sep).join("/");
  const noExt = posix.replace(/\.(md|markdown)$/i, "");
  if (noExt === "index" || noExt.endsWith("/index")) {
    const dir = noExt === "index" ? "" : noExt.slice(0, -"/index".length);
    return {
      url: dir ? `/${dir}/` : "/",
      outputPath: dir ? `${dir}/index.html` : "index.html",
    };
  }
  return { url: `/${noExt}/`, outputPath: `${noExt}/index.html` };
}

function makeExcerpt(body: string, maxLen = 200): string {
  const text = body
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[#>*_`[\]()!-]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

/** Load a single markdown file into a Page. */
export async function loadPage(sourceDir: string, relPath: string): Promise<Page> {
  const raw = await fs.readFile(path.join(sourceDir, relPath), "utf8");
  const { frontmatter, body } = parseFrontmatter(raw);
  const { url, outputPath } = pathsFor(relPath);
  return {
    sourcePath: relPath.split(path.sep).join("/"),
    url,
    outputPath,
    frontmatter,
    body,
    html: renderMarkdown(body),
    excerpt: makeExcerpt(body),
  };
}

/** Recursively find markdown files under dir, returning source-relative paths. */
export async function findMarkdownFiles(dir: string, base = dir): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await findMarkdownFiles(full, base)));
    else if (/\.(md|markdown)$/i.test(entry.name)) out.push(path.relative(base, full));
  }
  return out.sort();
}
