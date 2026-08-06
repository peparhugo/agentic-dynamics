import fs from "node:fs/promises";
import path from "node:path";
import { parseFrontmatter, titleFromSlug } from "./frontmatter.js";
import { createMarkdownRenderer } from "./markdown.js";
import { TemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";
import type { BuildOptions, BuildResult, Page, SiteConfig } from "./types.js";

const DEFAULT_SITE: SiteConfig = {
  title: "My Site",
  baseUrl: "http://localhost:4000",
  description: "",
};

async function* walk(dir: string): AsyncGenerator<string> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.isFile()) yield full;
  }
}

function slugFor(sourceDir: string, file: string): string {
  return path
    .relative(sourceDir, file)
    .replace(/\.md$/i, "")
    .split(path.sep)
    .join("/");
}

function outputMapping(slug: string): { url: string; outFile: string } {
  if (slug === "index" || slug.endsWith("/index")) {
    const base = slug === "index" ? "" : slug.slice(0, -"/index".length);
    return {
      url: base ? `/${base}/` : "/",
      outFile: path.join(...(base ? base.split("/") : []), "index.html"),
    };
  }
  return {
    url: `/${slug}/`,
    outFile: path.join(...slug.split("/"), "index.html"),
  };
}

function tagSlug(tag: string): string {
  return tag
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function sortByDateDesc(pages: Page[]): Page[] {
  return [...pages].sort(
    (a, b) => (b.meta.date?.getTime() ?? 0) - (a.meta.date?.getTime() ?? 0)
  );
}

async function writeOut(outDir: string, relFile: string, content: string): Promise<void> {
  const target = path.join(outDir, relFile);
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, content, "utf8");
}

/** Build the site: markdown pages, tag index pages, RSS feed, static passthrough. */
export async function buildSite(options: BuildOptions): Promise<BuildResult> {
  const site: SiteConfig = { ...DEFAULT_SITE, ...options.site };
  const engine = await TemplateEngine.fromDir(options.templateDir);
  const renderMarkdown = createMarkdownRenderer();

  const pages: Page[] = [];
  const staticFiles: string[] = [];
  let skippedDrafts = 0;

  for await (const file of walk(options.sourceDir)) {
    if (!/\.md$/i.test(file)) {
      staticFiles.push(file);
      continue;
    }
    const slug = slugFor(options.sourceDir, file);
    const raw = await fs.readFile(file, "utf8");
    const { meta, body } = parseFrontmatter(raw, titleFromSlug(slug));
    if (meta.draft && !options.includeDrafts) {
      skippedDrafts++;
      continue;
    }
    const { url, outFile } = outputMapping(slug);
    pages.push({ sourcePath: file, slug, url, outFile, meta, html: renderMarkdown(body) });
  }

  const sorted = sortByDateDesc(pages);
  await fs.mkdir(options.outDir, { recursive: true });

  // Pages
  for (const page of pages) {
    const html = engine.render(page.meta.layout, {
      content: page.html,
      page: { ...page.meta, ...page.meta.extra, url: page.url },
      pages: sorted.map(pageContext),
      site,
    });
    await writeOut(options.outDir, page.outFile, html);
  }

  // Tag index pages
  const byTag = new Map<string, Page[]>();
  for (const page of sorted) {
    for (const tag of page.meta.tags) {
      const list = byTag.get(tag) ?? [];
      list.push(page);
      byTag.set(tag, list);
    }
  }

  const tagPages: string[] = [];
  for (const [tag, tagged] of byTag) {
    const url = `/tags/${tagSlug(tag)}/`;
    const html = engine.render("tag", {
      content: "",
      tag,
      page: { title: `Tagged: ${tag}`, url, tags: [], date: null },
      pages: tagged.map(pageContext),
      site,
    });
    await writeOut(options.outDir, path.join("tags", tagSlug(tag), "index.html"), html);
    tagPages.push(url);
  }

  // All-tags overview
  if (byTag.size > 0) {
    const tags = [...byTag.entries()]
      .map(([tag, list]) => ({ tag, slug: tagSlug(tag), count: list.length, url: `/tags/${tagSlug(tag)}/` }))
      .sort((a, b) => a.tag.localeCompare(b.tag));
    const html = engine.render("tags", {
      content: "",
      tags,
      page: { title: "Tags", url: "/tags/", tags: [], date: null },
      site,
    });
    await writeOut(options.outDir, path.join("tags", "index.html"), html);
  }

  // RSS feed
  await writeOut(options.outDir, "feed.xml", generateRss(sorted, site));

  // Static passthrough (non-markdown files in source dir)
  for (const file of staticFiles) {
    const rel = path.relative(options.sourceDir, file);
    const target = path.join(options.outDir, rel);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.copyFile(file, target);
  }

  return { pages: sorted, tagPages, skippedDrafts, outDir: options.outDir };
}

function pageContext(page: Page): Record<string, unknown> {
  return {
    title: page.meta.title,
    date: page.meta.date,
    tags: page.meta.tags,
    draft: page.meta.draft,
    url: page.url,
    ...page.meta.extra,
  };
}
