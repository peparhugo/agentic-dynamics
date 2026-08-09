import fs from "fs";
import path from "path";
import fm from "front-matter";
import { Marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";
import type { Frontmatter, Page } from "../types";

const marked = new Marked(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code: string, lang: string) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return code;
    },
  })
);

export function parseFrontmatter(raw: string): {
  frontmatter: Frontmatter;
  body: string;
} {
  const parsed = fm<Frontmatter>(raw);
  return {
    frontmatter: parsed.attributes,
    body: parsed.body,
  };
}

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown) as string;
}

export function parseMarkdownFile(
  filePath: string,
  sourceDir: string,
  outputDir: string
): Page {
  const raw = fs.readFileSync(filePath, "utf-8");
  const { frontmatter, body } = parseFrontmatter(raw);
  const html = markdownToHtml(body);

  const relativePath = path.relative(sourceDir, filePath);
  const parsed = path.parse(relativePath);
  const slug = path.join(parsed.dir, parsed.name).replace(/\\/g, "/");
  const outputPath = path.join(
    outputDir,
    parsed.dir,
    `${parsed.name}.html`
  );

  return {
    frontmatter,
    content: body,
    html,
    slug: slug || "index",
    sourcePath: filePath,
    outputPath,
  };
}

export function loadPages(
  sourceDir: string,
  outputDir: string
): { pages: Page[]; drafts: Page[] } {
  const allPages: Page[] = [];
  const drafts: Page[] = [];

  function walk(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.name.endsWith(".md")) {
        const page = parseMarkdownFile(fullPath, sourceDir, outputDir);
        if (page.frontmatter.draft) {
          drafts.push(page);
        } else {
          allPages.push(page);
        }
      }
    }
  }

  walk(sourceDir);

  allPages.sort((a, b) => {
    const dateA = a.frontmatter.date
      ? new Date(a.frontmatter.date).getTime()
      : 0;
    const dateB = b.frontmatter.date
      ? new Date(b.frontmatter.date).getTime()
      : 0;
    return dateB - dateA;
  });

  return { pages: allPages, drafts };
}
