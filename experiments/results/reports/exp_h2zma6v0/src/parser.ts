import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { marked, type Token, type Tokens } from "marked";
import hljs from "highlight.js";
import type { Page, Frontmatter } from "./types.js";

function highlightExtension(): marked.MarkedExtension {
  return {
    renderer: {
      code(token: Tokens.Code): string {
        const lang = token.lang || "";
        const text = token.text;
        if (lang && hljs.getLanguage(lang)) {
          try {
            const result = hljs.highlight(text, { language: lang });
            return `<pre><code class="hljs language-${lang}">${result.value}</code></pre>\n`;
          } catch {
            // fall through
          }
        }
        try {
          const result = hljs.highlightAuto(text);
          return `<pre><code class="hljs">${result.value}</code></pre>\n`;
        } catch {
          return `<pre><code>${escapeHtml(text)}</code></pre>\n`;
        }
      },
    },
  };
}

marked.use(highlightExtension());

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function parseFrontmatter(raw: string): { frontmatter: Frontmatter; content: string } {
  const parsed = matter(raw);
  return {
    frontmatter: parsed.data as Frontmatter,
    content: parsed.content,
  };
}

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}

export async function loadPage(
  filePath: string,
  sourceDir: string,
  outputDir: string,
  baseUrl: string
): Promise<Page> {
  const raw = await fs.readFile(filePath, "utf-8");
  const { frontmatter, content } = parseFrontmatter(raw);
  const html = markdownToHtml(content);

  const relPath = path.relative(sourceDir, filePath);
  const parsed = path.parse(relPath);
  const urlPath = parsed.name === "index" ? parsed.dir : path.join(parsed.dir, parsed.name);
  const normalizedUrl = "/" + urlPath.replace(/\\/g, "/").replace(/\/$/, "") + "/";

  const outPath = path.join(outputDir, parsed.dir, parsed.name + ".html");

  // Ensure draft defaults to false if missing
  if (frontmatter.draft === undefined) {
    frontmatter.draft = false;
  }

  return {
    frontmatter,
    content,
    html,
    sourcePath: filePath,
    outputPath: outPath,
    url: normalizedUrl,
  };
}

// Parse a date string to ISO format for RSS, returns undefined if invalid
export function parseDate(value: string | undefined): Date | undefined {
  if (!value) return undefined;
  const d = new Date(value);
  return isNaN(d.getTime()) ? undefined : d;
}
