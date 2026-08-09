import fs from "node:fs/promises";
import path from "node:path";
import { loadContent, slugify, type Post } from "./content.js";
import { TemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";

export interface BuildOptions {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  baseUrl?: string;
  siteTitle?: string;
  siteDescription?: string;
  includeDrafts?: boolean;
  clean?: boolean;
}

export interface BuildResult {
  posts: Post[];
  tags: Map<string, Post[]>;
  /** Output-dir-relative paths of every file written. */
  files: string[];
}

async function writeFile(outDir: string, rel: string, content: string, files: string[]): Promise<void> {
  const full = path.join(outDir, rel);
  await fs.mkdir(path.dirname(full), { recursive: true });
  await fs.writeFile(full, content, "utf8");
  files.push(rel);
}

export function collectTags(posts: Post[]): Map<string, Post[]> {
  const tags = new Map<string, Post[]>();
  for (const post of posts) {
    for (const tag of post.tags) {
      const key = slugify(tag);
      const list = tags.get(key);
      if (list) list.push(post);
      else tags.set(key, [post]);
    }
  }
  return tags;
}

export async function buildSite(opts: BuildOptions): Promise<BuildResult> {
  const {
    sourceDir,
    templateDir,
    outDir,
    baseUrl = "http://localhost:3000",
    siteTitle = "My Site",
    siteDescription = "",
    includeDrafts = false,
    clean = true,
  } = opts;

  if (clean) await fs.rm(outDir, { recursive: true, force: true });
  await fs.mkdir(outDir, { recursive: true });

  const engine = await TemplateEngine.load(templateDir);
  const { posts, assets } = await loadContent(sourceDir, includeDrafts);
  const tags = collectTags(posts);
  const files: string[] = [];

  const site = { title: siteTitle, description: siteDescription, baseUrl, tags: [...tags.keys()].sort() };

  // Post pages: <slug>/index.html
  for (const post of posts) {
    const html = engine.renderLayout(post.layout, { ...post, content: post.html, site, posts });
    await writeFile(outDir, path.join(post.slug, "index.html"), html, files);
  }

  // Site index
  const indexHtml = engine.renderPage("index", { site, posts });
  await writeFile(outDir, "index.html", indexHtml, files);

  // Tag index pages: tags/<tag>/index.html
  const tagPage = engine.hasPage("tag") ? "tag" : "index";
  for (const [tag, tagPosts] of tags) {
    const html = engine.renderPage(tagPage, { site, posts: tagPosts, tag });
    await writeFile(outDir, path.join("tags", tag, "index.html"), html, files);
  }

  // RSS feed
  const rss = generateRss(posts, { title: siteTitle, description: siteDescription, baseUrl });
  await writeFile(outDir, "feed.xml", rss, files);

  // Pass-through assets from the source dir
  for (const rel of assets) {
    const dest = path.join(outDir, rel);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(path.join(sourceDir, rel), dest);
    files.push(rel);
  }

  return { posts, tags, files };
}
