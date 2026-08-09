import fs from "node:fs";
import path from "node:path";
import { parseFrontmatter } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { createTemplateEngine, type TemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";
import type { BuildResult, Page, SiteConfig } from "./types.js";

function walk(dir: string, base = dir): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full, base));
    else if (/\.(md|markdown)$/.test(entry.name)) out.push(path.relative(base, full));
  }
  return out.sort();
}

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function urlFor(sourcePath: string): { url: string; outputPath: string } {
  const noExt = sourcePath.replace(/\.(md|markdown)$/, "").split(path.sep).join("/");
  if (noExt === "index" || noExt.endsWith("/index")) {
    const dir = noExt === "index" ? "" : noExt.slice(0, -"/index".length);
    return { url: `/${dir}${dir ? "/" : ""}`, outputPath: path.join(dir, "index.html") };
  }
  return { url: `/${noExt}/`, outputPath: path.join(noExt, "index.html") };
}

/** Load and render all markdown pages from the source directory. */
export function loadPages(config: SiteConfig): Page[] {
  const files = walk(config.sourceDir);
  const pages: Page[] = [];
  for (const rel of files) {
    const raw = fs.readFileSync(path.join(config.sourceDir, rel), "utf8");
    const fallbackTitle = path.basename(rel).replace(/\.(md|markdown)$/, "");
    const { frontmatter, body } = parseFrontmatter(raw, fallbackTitle);
    if (frontmatter.draft && !config.includeDrafts) continue;
    const { url, outputPath } = urlFor(rel);
    pages.push({ sourcePath: rel, outputPath, url, frontmatter, body, html: renderMarkdown(body) });
  }
  // Newest first; undated pages sink to the bottom.
  pages.sort((a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0));
  return pages;
}

/** Group pages by tag (tag -> pages, preserving date order). */
export function collectTags(pages: Page[]): Map<string, Page[]> {
  const tags = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      if (!tags.has(tag)) tags.set(tag, []);
      tags.get(tag)!.push(page);
    }
  }
  return new Map([...tags.entries()].sort(([a], [b]) => a.localeCompare(b)));
}

function writeFile(outDir: string, relPath: string, content: string, written: string[]): void {
  const full = path.join(outDir, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
  written.push(relPath);
}

/** Build the whole site: pages, index, tag pages, RSS feed. */
export function buildSite(config: SiteConfig, engine?: TemplateEngine): BuildResult {
  const tpl = engine ?? createTemplateEngine(config.templateDir);
  const pages = loadPages(config);
  const tags = collectTags(pages);
  const written: string[] = [];

  const site = {
    title: config.siteTitle,
    description: config.siteDescription,
    baseUrl: config.baseUrl,
    tags: [...tags.keys()],
  };

  const indexPage = pages.find((p) => p.url === "/");
  const contentPages = pages.filter((p) => p !== indexPage);

  for (const page of pages) {
    const templateName =
      typeof page.frontmatter.template === "string" && tpl.hasTemplate(page.frontmatter.template)
        ? (page.frontmatter.template as string)
        : tpl.hasTemplate("post")
          ? "post"
          : "page";
    const html = tpl.render(
      templateName,
      { site, page, pages: contentPages, title: page.frontmatter.title },
      page.frontmatter.layout
    );
    writeFile(config.outDir, page.outputPath, html, written);
  }

  if (!indexPage) {
    const html = tpl.render("index", { site, pages: contentPages, title: config.siteTitle });
    writeFile(config.outDir, "index.html", html, written);
  }

  const tagPages: string[] = [];
  for (const [tag, tagged] of tags) {
    const slug = slugify(tag);
    const outPath = path.join("tags", slug, "index.html");
    const html = tpl.render("tag", { site, tag, pages: tagged, title: `Tag: ${tag}` });
    writeFile(config.outDir, outPath, html, written);
    tagPages.push(`/tags/${slug}/`);
  }

  const feedPages = contentPages.filter((p) => !p.frontmatter.draft);
  writeFile(config.outDir, "feed.xml", generateRss(feedPages, config), written);

  return { pages, tagPages, filesWritten: written };
}
