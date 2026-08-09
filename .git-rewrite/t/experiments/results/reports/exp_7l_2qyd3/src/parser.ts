import path from "node:path";
import { marked, Renderer } from "marked";
import hljs from "highlight.js";
import matter from "gray-matter";
import type { Frontmatter, Page } from "./types.js";
import { normalizeMarkdownPath } from "./utils.js";

const renderer = new Renderer();
const baseCode = renderer.code.bind(renderer);

renderer.code = function (token: { text: string; lang?: string; escaped?: boolean }): string {
  const { text, lang } = token;
  if (lang && hljs.getLanguage(lang)) {
    const highlighted = hljs.highlight(text, { language: lang }).value;
    return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>\n`;
  }
  return `<pre><code>${text}</code></pre>\n`;
};

marked.use({ renderer });

export function parseMarkdown(
  raw: string,
  sourcePath: string
): Pick<Page, "frontmatter" | "content" | "slug" | "sourcePath"> {
  const { data, content: mdBody } = matter(raw);

  const frontmatter: Frontmatter = {
    title: data.title ?? "Untitled",
    date: data.date ? String(data.date) : undefined,
    tags: data.tags ?? [],
    draft: data.draft ?? false,
    ...data,
  };

  if (!Array.isArray(frontmatter.tags)) {
    frontmatter.tags = [];
  }

  const htmlContent = marked.parse(mdBody, { async: false }) as string;

  const slug = normalizeMarkdownPath(path.parse(sourcePath).dir + "/" + path.parse(sourcePath).name)
    .replace(/\/index\.html$/, "")
    .replace(/^\//, "");

  return {
    frontmatter,
    content: htmlContent,
    slug,
    sourcePath,
  };
}

export function getPublishedPages(pages: Page[]): Page[] {
  return pages.filter((p) => !p.frontmatter.draft);
}

export function sortByDate(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });
}
