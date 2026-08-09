import fs from "node:fs";
import path from "node:path";
import { parseDocument, renderMarkdown, makeExcerpt } from "./content.js";
import { TemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";
import type { BuildResult, Post, SiteConfig } from "./types.js";

function walk(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Load and parse all posts from the source directory. */
export function loadPosts(site: SiteConfig): Post[] {
  const files = walk(site.sourceDir).filter((f) => f.endsWith(".md"));
  const posts: Post[] = [];
  for (const file of files) {
    const rel = path.relative(site.sourceDir, file);
    const fallbackTitle = path.basename(file, ".md");
    const { frontmatter, body } = parseDocument(fs.readFileSync(file, "utf8"), fallbackTitle);
    if (frontmatter.draft && !site.includeDrafts) continue;
    const slug = rel.replace(/\.md$/, "").split(path.sep).map(slugify).join("/");
    posts.push({
      slug,
      sourcePath: file,
      frontmatter,
      markdown: body,
      html: renderMarkdown(body),
      excerpt: makeExcerpt(body),
      url: `/${slug}/`,
    });
  }
  posts.sort((a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0));
  return posts;
}

/** Group posts by tag. */
export function buildTagIndex(posts: Post[]): Map<string, Post[]> {
  const index = new Map<string, Post[]>();
  for (const post of posts) {
    for (const tag of post.frontmatter.tags) {
      const key = slugify(tag);
      const list = index.get(key) ?? [];
      list.push(post);
      index.set(key, list);
    }
  }
  return index;
}

function writeFile(outDir: string, relPath: string, content: string, written: string[]): void {
  const full = path.join(outDir, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
  written.push(relPath);
}

/** Copy non-markdown files from source to output verbatim (static assets). */
function copyAssets(site: SiteConfig, written: string[]): void {
  for (const file of walk(site.sourceDir).filter((f) => !f.endsWith(".md"))) {
    const rel = path.relative(site.sourceDir, file);
    const dest = path.join(site.outDir, rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(file, dest);
    written.push(rel);
  }
}

/** Full site build: posts, index, tag pages, RSS, assets. */
export function buildSite(site: SiteConfig): BuildResult {
  const engine = new TemplateEngine(site.templateDir);
  const posts = loadPosts(site);
  const tagIndex = buildTagIndex(posts);
  const written: string[] = [];
  const siteCtx = { title: site.title, baseUrl: site.baseUrl };

  fs.mkdirSync(site.outDir, { recursive: true });

  for (const post of posts) {
    const html = engine.render(
      "post",
      { ...post.frontmatter, post, content: post.html, site: siteCtx },
      post.frontmatter.layout
    );
    writeFile(site.outDir, path.join(post.slug, "index.html"), html, written);
  }

  const tags = [...tagIndex.keys()].sort().map((tag) => ({ tag, count: tagIndex.get(tag)!.length, url: `/tags/${tag}/` }));

  if (engine.hasPage("index")) {
    const html = engine.render("index", { posts, tags, site: siteCtx, title: site.title });
    writeFile(site.outDir, "index.html", html, written);
  }

  if (engine.hasPage("tag")) {
    for (const [tag, tagPosts] of tagIndex) {
      const html = engine.render("tag", { tag, posts: tagPosts, site: siteCtx, title: `Tag: ${tag}` });
      writeFile(site.outDir, path.join("tags", tag, "index.html"), html, written);
    }
  }

  writeFile(site.outDir, "rss.xml", generateRss(posts, site), written);
  copyAssets(site, written);

  return { posts, tagIndex, pagesWritten: written };
}
