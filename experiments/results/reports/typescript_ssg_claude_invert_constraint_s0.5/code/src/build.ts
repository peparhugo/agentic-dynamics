import { promises as fs } from "node:fs";
import path from "node:path";
import { parseFrontmatter, type Frontmatter } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { loadTemplates } from "./templates.js";
import { generateRss } from "./rss.js";

export interface BuildOptions {
  source: string;
  templates: string;
  output: string;
  includeDrafts?: boolean;
  siteTitle?: string;
  siteUrl?: string;
  /** HTML snippet injected before </body> of every page (used by dev server). */
  injectHtml?: string;
}

export interface Page {
  /** Source path relative to source dir, e.g. "posts/hello.md" */
  sourcePath: string;
  /** Output path relative to output dir, e.g. "posts/hello/index.html" */
  outputPath: string;
  /** Site-absolute URL path, e.g. "/posts/hello/" */
  urlPath: string;
  data: Frontmatter;
  html: string;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[]; // tag names that got index pages
  skippedDrafts: number;
  written: string[]; // output-relative paths written
}

async function walk(dir: string, base = dir): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(abs, base)));
    else out.push(path.relative(base, abs));
  }
  return out;
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function toOutputPath(relSource: string): { outputPath: string; urlPath: string } {
  const noExt = relSource.replace(/\.(md|markdown)$/i, "");
  const parts = noExt.split(path.sep);
  if (parts[parts.length - 1] === "index") parts.pop();
  const urlPath = parts.length ? `/${parts.join("/")}/` : "/";
  const outputPath = path.join(...parts, "index.html");
  return { outputPath, urlPath };
}

function injectBeforeBodyClose(html: string, snippet: string): string {
  const idx = html.lastIndexOf("</body>");
  if (idx === -1) return html + snippet;
  return html.slice(0, idx) + snippet + html.slice(idx);
}

export async function build(opts: BuildOptions): Promise<BuildResult> {
  const engine = await loadTemplates(opts.templates);
  const files = await walk(opts.source);
  const written: string[] = [];
  const pages: Page[] = [];
  let skippedDrafts = 0;

  await fs.rm(opts.output, { recursive: true, force: true });
  await fs.mkdir(opts.output, { recursive: true });

  const writeOut = async (rel: string, contents: string | Buffer) => {
    const abs = path.join(opts.output, rel);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, contents);
    written.push(rel.split(path.sep).join("/"));
  };

  // 1. Parse all markdown files; copy everything else through verbatim.
  for (const rel of files) {
    if (!/\.(md|markdown)$/i.test(rel)) {
      await writeOut(rel, await fs.readFile(path.join(opts.source, rel)));
      continue;
    }
    const raw = await fs.readFile(path.join(opts.source, rel), "utf8");
    const { data, content } = parseFrontmatter(raw);
    if (data.draft && !opts.includeDrafts) {
      skippedDrafts++;
      continue;
    }
    const { outputPath, urlPath } = toOutputPath(rel);
    pages.push({
      sourcePath: rel.split(path.sep).join("/"),
      outputPath,
      urlPath,
      data,
      html: renderMarkdown(content),
    });
  }

  pages.sort((a, b) => (b.data.date?.getTime() ?? 0) - (a.data.date?.getTime() ?? 0));

  const site = {
    title: opts.siteTitle ?? "Site",
    url: (opts.siteUrl ?? "").replace(/\/+$/, ""),
  };
  const pageContext = (p: Page) => ({
    ...p.data,
    content: p.html,
    url: p.urlPath,
    site,
    pages: pages.map((q) => ({ ...q.data, url: q.urlPath })),
  });

  // 2. Render pages through their layout.
  for (const p of pages) {
    let html = engine.renderPage(p.data.layout, pageContext(p));
    if (opts.injectHtml) html = injectBeforeBodyClose(html, opts.injectHtml);
    await writeOut(p.outputPath, html);
  }

  // 3. Tag index pages at /tags/<slug>/.
  const byTag = new Map<string, Page[]>();
  for (const p of pages) {
    for (const tag of p.data.tags) {
      const list = byTag.get(tag) ?? [];
      list.push(p);
      byTag.set(tag, list);
    }
  }
  const tagLayout = engine.hasLayout("tag") ? "tag" : "default";
  for (const [tag, tagged] of byTag) {
    const context = {
      title: `Tag: ${tag}`,
      tag,
      date: null,
      tags: [],
      draft: false,
      layout: tagLayout,
      site,
      content: "",
      url: `/tags/${slugify(tag)}/`,
      pages: tagged.map((q) => ({ ...q.data, url: q.urlPath })),
    };
    let html = engine.renderPage(tagLayout, context);
    if (opts.injectHtml) html = injectBeforeBodyClose(html, opts.injectHtml);
    await writeOut(path.join("tags", slugify(tag), "index.html"), html);
  }

  // 4. RSS feed.
  await writeOut(
    "feed.xml",
    generateRss(pages, { title: site.title, url: site.url || "http://localhost" })
  );

  return { pages, tagPages: [...byTag.keys()], skippedDrafts, written };
}
