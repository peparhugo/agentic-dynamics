import { readdirSync, readFileSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { join, relative, extname, dirname } from "node:path";
import type { Page, Site, BuildOptions } from "./types.js";
import { parseFrontmatter } from "./frontmatter.js";
import { markdownToHtml } from "./markdown.js";
import { createRenderer } from "./render.js";
import { generateRss } from "./rss.js";

export function build(options: BuildOptions): Site {
  const { source, templates, output } = options;
  const pages = collectPages(source);
  const tags = buildTagIndex(pages);
  const site: Site = { pages, tags };
  const renderer = createRenderer(templates);

  mkdirSync(output, { recursive: true });

  for (const page of pages) {
    if (page.frontmatter.draft) continue;
    const html = renderer.render("post", {
      title: page.frontmatter.title,
      date: page.frontmatter.date ?? "",
      tags: page.frontmatter.tags ?? [],
      content: page.html,
      url: page.url,
    });
    const outPath = join(output, page.path.replace(/\.md$/, ".html"));
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, html);
  }

  const published = pages.filter((p) => !p.frontmatter.draft);
  const sorted = [...published].sort((a, b) => {
    const da = a.frontmatter.date ?? "";
    const db = b.frontmatter.date ?? "";
    return db.localeCompare(da);
  });

  const indexHtml = renderer.render("index", {
    title: "Home",
    posts: sorted.map((p) => ({
      title: p.frontmatter.title,
      date: p.frontmatter.date ?? "",
      tags: p.frontmatter.tags ?? [],
      url: p.url,
    })),
  });
  writeFileSync(join(output, "index.html"), indexHtml);

  for (const [tag, tagPages] of tags.entries()) {
    const tagHtml = renderer.render("tag", {
      title: `Tag: ${tag}`,
      tag,
      posts: tagPages.map((p) => ({
        title: p.frontmatter.title,
        date: p.frontmatter.date ?? "",
        url: p.url,
      })),
    });
    const tagDir = join(output, "tags");
    mkdirSync(tagDir, { recursive: true });
    writeFileSync(join(tagDir, `${tag}.html`), tagHtml);
  }

  const rss = generateRss(published, "http://localhost:3000");
  writeFileSync(join(output, "feed.xml"), rss);

  copyAssets(source, output);

  return site;
}

function collectPages(source: string): Page[] {
  const pages: Page[] = [];
  walkDir(source, source, pages);
  return pages;
}

function walkDir(root: string, dir: string, pages: Page[]): void {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      walkDir(root, full, pages);
    } else if (extname(entry.name) === ".md") {
      const raw = readFileSync(full, "utf-8");
      const { frontmatter, content } = parseFrontmatter(raw);
      const html = markdownToHtml(content);
      const rel = relative(root, full);
      const url = "/" + rel.replace(/\.md$/, ".html");
      pages.push({ path: rel, url, frontmatter, content, html });
    }
  }
}

function buildTagIndex(pages: Page[]): Map<string, Page[]> {
  const map = new Map<string, Page[]>();
  for (const page of pages) {
    if (page.frontmatter.draft) continue;
    for (const tag of page.frontmatter.tags ?? []) {
      const list = map.get(tag) ?? [];
      list.push(page);
      map.set(tag, list);
    }
  }
  return map;
}

function copyAssets(source: string, output: string): void {
  copyNonMd(source, source, output);
}

function copyNonMd(root: string, dir: string, out: string): void {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const src = join(dir, entry.name);
    const dst = join(out, relative(root, src));
    if (entry.isDirectory()) {
      mkdirSync(dst, { recursive: true });
      copyNonMd(root, src, out);
    } else if (extname(entry.name) !== ".md") {
      mkdirSync(dirname(dst), { recursive: true });
      writeFileSync(dst, readFileSync(src));
    }
  }
}
