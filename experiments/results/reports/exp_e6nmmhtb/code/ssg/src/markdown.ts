import matter from "gray-matter";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import type { Page, Frontmatter } from "./types.js";

const md = new MarkdownIt({
  html: true,
  highlight(str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return (
          '<pre><code class="hljs language-' +
          lang +
          '">' +
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
          "</code></pre>"
        );
      } catch {
        // fall through
      }
    }
    return '<pre><code class="hljs">' + md.utils.escapeHtml(str) + "</code></pre>";
  },
});

export function parseMarkdown(raw: string, filePath: string): Page {
  const { data, content } = matter(raw);

  const frontmatter: Frontmatter = {
    title: data.title ?? "Untitled",
    date: data.date ? String(data.date) : undefined,
    tags: parseTags(data.tags),
    draft: data.draft === true || data.draft === "true",
  };

  for (const [k, v] of Object.entries(data)) {
    if (!(k in frontmatter)) {
      frontmatter[k] = v;
    }
  }

  const html = md.render(content);
  const url = filePathToUrl(filePath);
  const isPost = filePath.startsWith("posts/") || filePath.startsWith("/posts/");

  return { path: filePath, url, frontmatter, content, html, isPost };
}

function parseTags(tags: unknown): string[] {
  if (Array.isArray(tags)) return tags.map(String);
  if (typeof tags === "string") return tags.split(",").map((t) => t.trim()).filter(Boolean);
  return [];
}

function filePathToUrl(filePath: string): string {
  let url = filePath.replace(/\\/g, "/");
  url = url.replace(/^\.?\//, "");
  if (url.endsWith(".md")) url = url.slice(0, -3);
  if (url.endsWith("/index")) url = url.slice(0, -5) || "/";
  if (url === "index") url = "";
  return "/" + url.replace(/\/$/, "") + "/";
}
