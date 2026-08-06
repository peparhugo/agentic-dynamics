import { readFileSync, readdirSync, statSync, writeFileSync, mkdirSync, copyFileSync, existsSync } from "node:fs";
import { join, dirname, relative, basename, extname } from "node:path";
import matter from "gray-matter";
import { Marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";
import Handlebars from "handlebars";
import type { Post, PostMeta, TagPage, SiteData } from "./types.js";

const marked = new Marked(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code: string, lang: string) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
  })
);

function slugify(name: string): string {
  return basename(name, extname(name));
}

function parseFile(path: string): Post | null {
  const raw = readFileSync(path, "utf-8");
  const { data, content } = matter(raw);
  const meta = data as Partial<PostMeta>;
  if (meta.draft) return null;
  const title = meta.title ?? slugify(path);
  const date = meta.date ?? "";
  const tags = meta.tags ?? [];
  const html = marked.parse(content) as string;
  return { title, date: String(date), tags: Array.isArray(tags) ? tags : [tags].filter(Boolean), draft: !!meta.draft, slug: slugify(path), html, raw: content };
}

function collectFiles(dir: string): string[] {
  const result: string[] = [];
  function walk(d: string) {
    for (const entry of readdirSync(d)) {
      const full = join(d, entry);
      const s = statSync(full);
      if (s.isDirectory()) { walk(full); }
      else if (entry.endsWith(".md")) { result.push(full); }
    }
  }
  walk(dir);
  return result;
}

export function build(sourceDir: string, templateDir: string, outputDir: string): SiteData {
  const files = collectFiles(sourceDir);
  const posts: Post[] = [];
  for (const f of files) {
    const p = parseFile(f);
    if (p) posts.push(p);
  }
  posts.sort((a, b) => (b.date || "").localeCompare(a.date || ""));

  Handlebars.registerHelper("formatDate", (d: string) => {
    try { return new Date(d).toISOString().slice(0, 10); } catch { return d; }
  });

  const partials: Record<string, string> = {};
  const partialsDir = join(templateDir, "partials");
  if (existsSync(partialsDir)) {
    for (const f of readdirSync(partialsDir)) {
      if (f.endsWith(".hbs") || f.endsWith(".handlebars")) {
        partials[basename(f, extname(f))] = readFileSync(join(partialsDir, f), "utf-8");
      }
    }
  }

  for (const [name, src] of Object.entries(partials)) {
    Handlebars.registerPartial(name, src);
  }

  const layoutSrc = readFileSync(join(templateDir, "layout.hbs"), "utf-8");
  const layout = Handlebars.compile(layoutSrc);

  const postTemplate = existsSync(join(templateDir, "post.hbs"))
    ? Handlebars.compile(readFileSync(join(templateDir, "post.hbs"), "utf-8"))
    : null;

  const indexTemplate = existsSync(join(templateDir, "index.hbs"))
    ? Handlebars.compile(readFileSync(join(templateDir, "index.hbs"), "utf-8"))
    : null;

  const tagTemplate = existsSync(join(templateDir, "tag.hbs"))
    ? Handlebars.compile(readFileSync(join(templateDir, "tag.hbs"), "utf-8"))
    : null;

  if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });

  const tagMap = new Map<string, Post[]>();
  for (const post of posts) {
    for (const tag of post.tags) {
      if (!tagMap.has(tag)) tagMap.set(tag, []);
      tagMap.get(tag)!.push(post);
    }
  }

  const tagPages: TagPage[] = [];

  for (const [tag, tagPosts] of tagMap) {
    let tagHtml = "";
    if (tagTemplate) {
      tagHtml = tagTemplate({ tag, posts: tagPosts, allPosts: posts, allTags: [...tagMap.keys()].sort() });
    }
    const pageContent = layout({ content: tagHtml, title: `Tag: ${tag}`, posts, tags: [...tagMap.keys()].sort(), tag, tagPosts });
    const tagDir = join(outputDir, "tags", tag);
    mkdirSync(tagDir, { recursive: true });
    writeFileSync(join(tagDir, "index.html"), pageContent);
    tagPages.push({ tag, posts: tagPosts, html: pageContent });
  }

  if (indexTemplate) {
    const indexContent = indexTemplate({ posts, tags: [...tagMap.keys()].sort() });
    const indexPage = layout({ content: indexContent, title: "Home", posts, tags: [...tagMap.keys()].sort() });
    writeFileSync(join(outputDir, "index.html"), indexPage);
  }

  for (const post of posts) {
    let body = "";
    if (postTemplate) {
      body = postTemplate({ post, posts, ...post });
    } else {
      body = post.html;
    }
    const html = layout({ content: body, title: post.title, post, posts, tags: [...tagMap.keys()].sort() });
    const outPath = join(outputDir, post.slug, "index.html");
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, html);
  }

  const assetsDir = join(templateDir, "assets");
  if (existsSync(assetsDir)) {
    copyAssets(assetsDir, outputDir);
  }

  const rss = buildRss(posts);
  writeFileSync(join(outputDir, "feed.xml"), rss);

  return { posts, tags: tagPages, rss };
}

function copyAssets(src: string, dest: string) {
  for (const entry of readdirSync(src)) {
    const srcPath = join(src, entry);
    const destPath = join(dest, relative(src, srcPath));
    if (statSync(srcPath).isDirectory()) {
      if (!existsSync(destPath)) mkdirSync(destPath, { recursive: true });
      copyAssets(srcPath, destPath);
    } else {
      mkdirSync(dirname(destPath), { recursive: true });
      copyFileSync(srcPath, destPath);
    }
  }
}

function buildRss(posts: Post[]): string {
  const items = posts.map(p => {
    const date = p.date ? new Date(p.date).toUTCString() : new Date().toUTCString();
    return `    <item>
      <title><![CDATA[${p.title}]]></title>
      <link>/${p.slug}/</link>
      <guid isPermaLink="true">/${p.slug}/</guid>
      <pubDate>${date}</pubDate>
      <description><![CDATA[${p.html.slice(0, 500)}]]></description>
    </item>`;
  }).join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Site</title>
    <link>/</link>
    <description>Generated static site</description>
    <language>en</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="/feed.xml" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>`;
}
