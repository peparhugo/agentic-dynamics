import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync } from "node:fs";
import { join, relative, dirname, basename, extname } from "node:path";
import fm from "front-matter";
import { marked } from "marked";
import hljs from "highlight.js";
import type { Post } from "./types.js";

export function parseFrontmatter(filePath: string): Post {
  const raw = readFileSync(filePath, "utf-8");
  const { attributes, body } = fm<{
    title?: string;
    date?: string;
    tags?: string | string[];
    draft?: boolean;
  }>(raw);

  const slug = basename(filePath, extname(filePath));
  const tags = attributes.tags
    ? Array.isArray(attributes.tags)
      ? attributes.tags
      : attributes.tags.split(",").map((t: string) => t.trim())
    : [];

  return {
    title: attributes.title ?? slug.replace(/-/g, " "),
    date: attributes.date ? new Date(attributes.date) : undefined,
    tags,
    draft: attributes.draft ?? false,
    content: body,
    slug,
    raw,
  };
}

marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }) {
      if (lang && hljs.getLanguage(lang)) {
        const highlighted = hljs.highlight(text, { language: lang }).value;
        return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>\n`;
      }
      return `<pre><code>${text}</code></pre>\n`;
    },
  },
});

export function renderMarkdown(content: string): string {
  return marked.parse(content, { async: false }) as string;
}

export function ensureDir(dir: string): void {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

export function copyFile(src: string, dest: string): void {
  ensureDir(dirname(dest));
  writeFileSync(dest, readFileSync(src));
}

export function collectFiles(dir: string, ext: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      results.push(...collectFiles(full, ext));
    } else if (statSync(full).isFile() && full.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

export function pathToUrl(filePath: string, base: string, outputDir: string): string {
  const rel = relative(base, filePath);
  const withoutExt = rel.replace(/\.(html|md)$/, "");
  if (withoutExt.endsWith("index")) {
    return "/" + dirname(withoutExt).replace(/\\/g, "/") + "/";
  }
  return "/" + withoutExt.replace(/\\/g, "/") + "/";
}
