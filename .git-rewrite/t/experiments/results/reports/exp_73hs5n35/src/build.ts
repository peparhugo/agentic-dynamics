import fs from "node:fs/promises";
import path from "node:path";
import Handlebars from "handlebars";
import { findMarkdownFiles, loadPage } from "./content.js";
import { loadTemplates, type TemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";
import type { BuildOptions, BuildResult, Page, SiteConfig } from "./types.js";

const DEFAULT_SITE: SiteConfig = {
  title: "My Site",
  url: "http://localhost:3000",
  description: "",
};

function pickLayout(engine: TemplateEngine, page: Page): string {
  if (page.frontmatter.layout) return page.frontmatter.layout;
  if (engine.has("post")) return "post";
  return "default";
}

function pageContext(page: Page, site: SiteConfig, extra: Record<string, unknown> = {}) {
  return {
    site,
    page: { ...page.frontmatter, url: page.url, excerpt: page.excerpt },
    title: page.frontmatter.title,
    date: page.frontmatter.date,
    tags: page.frontmatter.tags,
    content: new Handlebars.SafeString(page.html),
    ...extra,
  };
}

function injectInto(html: string, script: string): string {
  if (html.includes("</body>")) return html.replace("</body>", `${script}\n</body>`);
  return html + script;
}

async function write(outputDir: string, rel: string, contents: string, written: string[]) {
  const full = path.join(outputDir, rel);
  await fs.mkdir(path.dirname(full), { recursive: true });
  await fs.writeFile(full, contents, "utf8");
  written.push(rel);
}

/** Collect pages grouped by tag. */
export function collectTags(pages: Page[]): Map<string, Page[]> {
  const tags = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      const list = tags.get(tag) ?? [];
      list.push(page);
      tags.set(tag, list);
    }
  }
  for (const list of tags.values()) {
    list.sort((a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0));
  }
  return tags;
}

/** Build the whole site: pages, tag indexes, index, RSS feed. */
export async function buildSite(options: BuildOptions): Promise<BuildResult> {
  const site: SiteConfig = { ...DEFAULT_SITE, ...options.site };
  const engine = await loadTemplates(options.templateDir);
  const written: string[] = [];

  const files = await findMarkdownFiles(options.sourceDir);
  const all = await Promise.all(files.map((f) => loadPage(options.sourceDir, f)));
  const pages = all.filter((p) => options.drafts || !p.frontmatter.draft);

  const byDateDesc = [...pages].sort(
    (a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0),
  );
  const postList = byDateDesc.map((p) => ({
    ...p.frontmatter,
    url: p.url,
    excerpt: p.excerpt,
  }));

  const finish = (html: string) => (options.injectScript ? injectInto(html, options.injectScript) : html);

  // Content pages
  for (const page of pages) {
    const html = engine.render(pickLayout(engine, page), pageContext(page, site, { posts: postList }));
    await write(options.outputDir, page.outputPath, finish(html), written);
  }

  // Tag index pages
  const tags = collectTags(pages);
  const tagLayout = engine.has("tag") ? "tag" : "default";
  for (const [tag, tagged] of tags) {
    const html = engine.render(tagLayout, {
      site,
      title: `Tag: ${tag}`,
      tag,
      posts: tagged.map((p) => ({ ...p.frontmatter, url: p.url, excerpt: p.excerpt })),
      content: "",
    });
    await write(options.outputDir, path.join("tags", tag, "index.html"), finish(html), written);
  }

  // Site index (only if no source index.md provided one)
  if (!pages.some((p) => p.outputPath === "index.html")) {
    const indexLayout = engine.has("index") ? "index" : "default";
    const html = engine.render(indexLayout, {
      site,
      title: site.title,
      posts: postList,
      tags: [...tags.keys()].sort(),
      content: "",
    });
    await write(options.outputDir, "index.html", finish(html), written);
  }

  // RSS
  await write(options.outputDir, "feed.xml", generateRss(pages, site), written);

  return { pages, tags, written };
}
