import { promises as fs } from "node:fs";
import path from "node:path";
import { parseFrontmatter, type Frontmatter } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { createTemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";

export interface BuildOptions {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  /** Include pages marked `draft: true` (default false). */
  drafts?: boolean;
  siteTitle?: string;
  siteDescription?: string;
  siteUrl?: string;
  /** Extra HTML injected before </body> of every page (used for live reload). */
  injectHtml?: string;
}

export interface Page {
  /** Path of the source file relative to sourceDir. */
  sourcePath: string;
  /** Site-absolute URL, e.g. "/posts/hello/". */
  url: string;
  /** Output path relative to outputDir. */
  outputPath: string;
  frontmatter: Frontmatter;
  /** Rendered Markdown body (no layout). */
  html: string;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  outputFiles: string[];
}

export async function build(opts: BuildOptions): Promise<BuildResult> {
  const engine = await createTemplateEngine(opts.templateDir);
  const site = {
    title: opts.siteTitle ?? "Site",
    description: opts.siteDescription ?? "",
    url: (opts.siteUrl ?? "http://localhost:3000").replace(/\/+$/, ""),
  };

  const files = await walkMarkdown(opts.sourceDir);
  const pages: Page[] = [];
  for (const file of files) {
    const rel = path.relative(opts.sourceDir, file);
    const { frontmatter, body } = parseFrontmatter(await fs.readFile(file, "utf8"));
    if (frontmatter.draft && !opts.drafts) continue;
    const { url, outputPath } = routeFor(rel);
    pages.push({ sourcePath: rel, url, outputPath, frontmatter, html: renderMarkdown(body) });
  }
  pages.sort(
    (a, b) =>
      (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0) ||
      a.sourcePath.localeCompare(b.sourcePath)
  );

  await fs.rm(opts.outputDir, { recursive: true, force: true });
  await fs.mkdir(opts.outputDir, { recursive: true });

  const outputFiles: string[] = [];
  const writeOut = async (relPath: string, content: string) => {
    const abs = path.join(opts.outputDir, relPath);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, content, "utf8");
    outputFiles.push(relPath);
  };

  // Pages
  for (const page of pages) {
    const layout = engine.hasLayout(page.frontmatter.layout) ? page.frontmatter.layout : "default";
    let html = engine.render(layout, {
      content: page.html,
      page: { ...page.frontmatter, url: page.url },
      site,
      pages: publicPageList(pages),
    });
    html = inject(html, opts.injectHtml);
    await writeOut(page.outputPath, html);
  }

  // Tag index pages
  const tags = collectTags(pages);
  const tagPages: string[] = [];
  for (const [tag, tagged] of tags) {
    const url = `/tags/${slugify(tag)}/`;
    const layout = engine.hasLayout("tag") ? "tag" : "default";
    let html = engine.render(layout, {
      content: "",
      tag,
      page: { title: `Tag: ${tag}`, url, tags: [], date: null, draft: false },
      site,
      pages: publicPageList(tagged),
    });
    html = inject(html, opts.injectHtml);
    await writeOut(path.join("tags", slugify(tag), "index.html"), html);
    tagPages.push(url);
  }

  // RSS
  await writeOut(
    "feed.xml",
    generateRss(pages, { title: site.title, description: site.description, siteUrl: site.url })
  );

  return { pages, tagPages, outputFiles };
}

/** "posts/hello.md" -> url "/posts/hello/", output "posts/hello/index.html".
 *  "index.md" -> "/" -> "index.html". */
export function routeFor(relSourcePath: string): { url: string; outputPath: string } {
  const noExt = relSourcePath.replace(/\.(md|markdown)$/i, "");
  const parts = noExt.split(path.sep).map(slugifyPathSegment);
  if (parts[parts.length - 1] === "index") parts.pop();
  const url = parts.length ? `/${parts.join("/")}/` : "/";
  const outputPath = path.join(...parts, "index.html");
  return { url, outputPath };
}

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function slugifyPathSegment(s: string): string {
  const slug = slugify(s);
  return slug || "untitled";
}

export function collectTags(pages: Page[]): Map<string, Page[]> {
  const map = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      const list = map.get(tag) ?? [];
      list.push(page);
      map.set(tag, list);
    }
  }
  return map;
}

function publicPageList(pages: Page[]) {
  return pages.map((p) => ({ ...p.frontmatter, url: p.url }));
}

function inject(html: string, snippet?: string): string {
  if (!snippet) return html;
  return html.includes("</body>")
    ? html.replace("</body>", `${snippet}\n</body>`)
    : html + snippet;
}

async function walkMarkdown(dir: string): Promise<string[]> {
  const out: string[] = [];
  async function walk(current: string): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (/\.(md|markdown)$/i.test(entry.name)) out.push(full);
    }
  }
  await walk(dir);
  return out.sort();
}
