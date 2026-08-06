import path from "node:path";
import fs from "node:fs";
import { parseFrontmatter } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { Renderer } from "./renderer.js";
import { buildTagIndex } from "./tags.js";
import { generateRSS } from "./rss.js";
import type { Frontmatter } from "./frontmatter.js";

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle?: string;
  siteDescription?: string;
  siteUrl?: string;
}

export interface Page {
  frontmatter: Frontmatter;
  html: string;
  path: string;
}

export async function buildSite(config: SiteConfig): Promise<Page[]> {
  const { sourceDir, templateDir, outputDir, siteTitle, siteDescription, siteUrl } = config;

  fs.mkdirSync(outputDir, { recursive: true });

  const renderer = new Renderer(templateDir);
  renderer.registerPartials();

  const mdFiles = collectMarkdownFiles(sourceDir);
  const parsed = mdFiles.map((f) => {
    const raw = fs.readFileSync(f, "utf-8");
    const { frontmatter, content } = parseFrontmatter(raw);
    const slug = frontmatter.slug || path.basename(f, path.extname(f));
    return { frontmatter: { ...frontmatter, slug }, content, sourcePath: f, slug };
  });

  const pages: Page[] = [];

  for (const entry of parsed) {
    if (entry.frontmatter.draft) continue;

    const bodyHtml = renderMarkdown(entry.content);
    const pageHtml = renderer.renderPage("post", {
      ...entry.frontmatter,
      body: bodyHtml,
      layout: entry.frontmatter.layout,
      siteTitle: siteTitle ?? "My Site",
    });

    const outPath = path.join(outputDir, `${entry.slug}.html`);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, pageHtml);

    pages.push({ frontmatter: entry.frontmatter, html: pageHtml, path: outPath });
  }

  const published = pages
    .map((p) => p.frontmatter)
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));

  if (published.length > 0) {
    const indexHtml = renderer.renderPage("index", {
      posts: published,
      siteTitle: siteTitle ?? "My Site",
      layout: "default",
    });
    fs.writeFileSync(path.join(outputDir, "index.html"), indexHtml);

    const tags = buildTagIndex(published);
    const tagsDir = path.join(outputDir, "tags");
    fs.mkdirSync(tagsDir, { recursive: true });

    for (const { tag, posts } of tags) {
      const tagHtml = renderer.renderPage("tag", {
        tag,
        posts,
        siteTitle: siteTitle ?? "My Site",
        layout: "default",
      });
      fs.writeFileSync(path.join(tagsDir, `${tag}.html`), tagHtml);
    }

    const tagsIndexHtml = renderer.renderPage("tags", {
      tags,
      siteTitle: siteTitle ?? "My Site",
      layout: "default",
    });
    fs.writeFileSync(path.join(outputDir, "tags.html"), tagsIndexHtml);
  }

  if (siteUrl) {
    const feed = generateRSS({
      title: siteTitle ?? "My Site",
      description: siteDescription ?? "",
      siteUrl,
      posts: published.map((p) => ({ ...p })),
    });
    fs.writeFileSync(path.join(outputDir, "feed.xml"), feed);
  }

  copyStaticAssets(sourceDir, outputDir);

  return pages;
}

function collectMarkdownFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) return files;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectMarkdownFiles(full));
    } else if (entry.name.endsWith(".md")) {
      files.push(full);
    }
  }
  return files;
}

function copyStaticAssets(sourceDir: string, outputDir: string): void {
  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    const src = path.join(sourceDir, entry.name);
    if (entry.isDirectory()) continue;
    if (entry.name.endsWith(".md")) continue;
    const dst = path.join(outputDir, entry.name);
    fs.copyFileSync(src, dst);
  }
}
