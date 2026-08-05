import * as fs from "fs";
import * as path from "path";
import { BuildContext, Post, TagIndex, SiteConfig } from "./types";
import { collectPosts } from "./parser";
import { initMarked, markdownToHtml } from "./markdown";
import { registerPartials, registerHelpers, renderTemplate } from "./template";
import { generateRssFeed } from "./rss";

export function loadConfig(sourceDir: string): SiteConfig {
  const configPath = path.join(sourceDir, "config.yaml");
  const defaults: SiteConfig = {
    title: path.basename(path.resolve(sourceDir)),
    description: "",
    url: "http://localhost:3000",
  };

  if (!fs.existsSync(configPath)) return defaults;

  try {
    const yaml = require("js-yaml");
    const raw = fs.readFileSync(configPath, "utf-8");
    const userConfig = yaml.load(raw) as Partial<SiteConfig>;
    return { ...defaults, ...userConfig };
  } catch {
    return defaults;
  }
}

export function buildPosts(posts: Post[]): Post[] {
  for (const post of posts) {
    post.html = markdownToHtml(post.body);
  }
  return posts;
}

export function buildTagIndexes(posts: Post[]): TagIndex[] {
  const published = posts.filter((p) => !p.frontmatter.draft);
  const tagMap = new Map<string, Post[]>();

  for (const post of published) {
    const tags = post.frontmatter.tags || [];
    for (const tag of tags) {
      if (!tagMap.has(tag)) tagMap.set(tag, []);
      tagMap.get(tag)!.push(post);
    }
  }

  const indexes: TagIndex[] = [];
  for (const [tag, tagPosts] of tagMap) {
    indexes.push({
      tag,
      posts: tagPosts,
      url: `/tags/${slugifyTag(tag)}.html`,
    });
  }
  return indexes;
}

function slugifyTag(tag: string): string {
  return tag
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function buildSite(sourceDir: string, templateDir: string, outputDir: string): BuildContext {
  registerHelpers();
  registerPartials(templateDir);
  initMarked();

  const config = loadConfig(sourceDir);
  const posts = collectPosts(sourceDir);
  buildPosts(posts);
  const tags = buildTagIndexes(posts);

  const ctx: BuildContext = {
    posts,
    tags,
    config,
    sourceDir,
    templateDir,
    outputDir,
  };

  writeSite(ctx);
  return ctx;
}

function writeSite(ctx: BuildContext): void {
  if (fs.existsSync(ctx.outputDir)) {
    fs.rmSync(ctx.outputDir, { recursive: true });
  }
  fs.mkdirSync(ctx.outputDir, { recursive: true });

  const published = ctx.posts.filter((p) => !p.frontmatter.draft);
  published.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  writeFile(ctx, "index.html", renderTemplate(ctx.templateDir, "index", {
    posts: published,
    config: ctx.config,
  }));

  for (const post of published) {
    const layout = post.frontmatter.layout;
    const html = renderTemplate(ctx.templateDir, "post", {
      post,
      config: ctx.config,
    }, layout);
    writeFile(ctx, post.url, html);
  }

  const tagsDir = path.join(ctx.outputDir, "tags");
  fs.mkdirSync(tagsDir, { recursive: true });
  for (const tagIdx of ctx.tags) {
    const html = renderTemplate(ctx.templateDir, "tag", {
      tag: tagIdx,
      posts: tagIdx.posts,
      config: ctx.config,
    });
    writeFile(ctx, tagIdx.url, html);
  }

  const tagsPage = renderTemplate(ctx.templateDir, "tags-index", {
    tags: ctx.tags,
    config: ctx.config,
  });
  writeFile(ctx, "/tags.html", tagsPage);

  const rssXml = generateRssFeed(ctx);
  writeRaw(ctx, "/rss.xml", rssXml);

  copyStatic(ctx);
}

function writeFile(ctx: BuildContext, url: string, html: string): void {
  const filePath = path.join(ctx.outputDir, url.replace(/^\//, ""));
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(filePath, html, "utf-8");
}

function writeRaw(ctx: BuildContext, url: string, content: string): void {
  const filePath = path.join(ctx.outputDir, url.replace(/^\//, ""));
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(filePath, content, "utf-8");
}

function copyStatic(ctx: BuildContext): void {
  const staticDir = path.join(ctx.sourceDir, "static");
  if (!fs.existsSync(staticDir)) return;
  copyDir(staticDir, ctx.outputDir);
}

function copyDir(src: string, dest: string): void {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

export { generateRssFeed };
