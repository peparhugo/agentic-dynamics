import matter from "gray-matter";
import { Marked } from "marked";
import hljs from "highlight.js";
import type { Frontmatter } from "./types.js";

/** Normalize raw frontmatter values into a typed Frontmatter object. */
export function normalizeFrontmatter(raw: Record<string, unknown>, fallbackTitle: string): Frontmatter {
  const title = typeof raw.title === "string" && raw.title.trim() !== "" ? raw.title : fallbackTitle;

  let date: Date | null = null;
  if (raw.date instanceof Date) {
    date = raw.date;
  } else if (typeof raw.date === "string" && raw.date.trim() !== "") {
    const parsed = new Date(raw.date);
    if (!Number.isNaN(parsed.getTime())) date = parsed;
  }

  let tags: string[] = [];
  if (Array.isArray(raw.tags)) {
    tags = raw.tags.map(String).map((t) => t.trim()).filter(Boolean);
  } else if (typeof raw.tags === "string") {
    tags = raw.tags.split(",").map((t) => t.trim()).filter(Boolean);
  }

  const draft = raw.draft === true || raw.draft === "true";

  return { ...raw, title, date, tags, draft, layout: typeof raw.layout === "string" ? raw.layout : undefined };
}

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

/** Parse a markdown document with optional YAML frontmatter. */
export function parseDocument(source: string, fallbackTitle = "Untitled"): ParsedDocument {
  const { data, content } = matter(source);
  return { frontmatter: normalizeFrontmatter(data, fallbackTitle), body: content };
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const marked = new Marked({
  gfm: true,
  renderer: {
    code(code: string, infostring: string | undefined): string {
      const lang = (infostring ?? "").trim().split(/\s+/)[0] ?? "";
      if (lang && hljs.getLanguage(lang)) {
        const { value } = hljs.highlight(code, { language: lang });
        return `<pre><code class="hljs language-${lang}">${value}</code></pre>\n`;
      }
      return `<pre><code class="hljs">${escapeHtml(code)}</code></pre>\n`;
    },
  },
});

/** Render markdown to HTML with syntax-highlighted code blocks. */
export function renderMarkdown(markdown: string): string {
  return marked.parse(markdown) as string;
}

/** Plain-text excerpt of the first `maxLength` characters. */
export function makeExcerpt(markdown: string, maxLength = 280): string {
  const text = markdown
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[#>*_~-]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}
