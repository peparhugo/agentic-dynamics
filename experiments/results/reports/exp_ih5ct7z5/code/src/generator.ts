import fs from "fs";
import path from "path";
import { Post, SiteConfig } from "./types";
import { loadPosts } from "./frontmatter";
import { markdownToHtml } from "./markdown";
import { loadTemplates, renderPage, TemplateContext } from "./renderer";
import { writeRssFeed } from "./rss";
import { buildTagIndex, generateTagPages } from "./tags";
import { CopyOptions } from "fs";

export function generateSite(
  sourceDir: string,
  templateDir: string,
  outputDir: string,
  config: SiteConfig
): void {
  const posts = loadPosts(sourceDir);

  const { templates, layouts } = loadTemplates(templateDir);

  for (const post of posts) {
    post.html = markdownToHtml(post.content);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  for (const post of posts) {
    const context: TemplateContext = {
      content: post.html,
      title: post.frontmatter.title,
      date: post.frontmatter.date,
      tags: post.frontmatter.tags,
      url: post.url,
      site: {
        ...config,
        posts,
        tags: [],
      },
    };

    let html: string;
    try {
      html = renderPage("post", templates, layouts, context);
    } catch {
      html = renderPage("page", templates, layouts, context);
    }

    const outPath = path.join(outputDir, post.slug + ".html");
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, html, "utf-8");
  }

  const publishedPosts = posts.filter((p) => !p.frontmatter.draft);
  const { tags, tagList } = buildTagIndex(publishedPosts);

  const indexContext: TemplateContext = {
    content: "",
    title: config.title,
    tags: [],
    url: "/",
    site: {
      ...config,
      posts: publishedPosts,
      tags: tagList,
    },
  };

  let indexHtml: string;
  if (templates.index) {
    indexHtml = renderPage("index", templates, layouts, indexContext);
  } else {
    indexHtml = buildDefaultIndex(config.title, publishedPosts);
  }
  fs.writeFileSync(path.join(outputDir, "index.html"), indexHtml, "utf-8");

  generateTagPages(tags, tagList, templates, layouts, outputDir, publishedPosts, config);

  writeRssFeed(outputDir, publishedPosts, config);

  copyStatic(templateDir, outputDir);
}

function buildDefaultIndex(title: string, posts: Post[]): string {
  const items = posts
    .map(
      (p) =>
        `<li><a href="${p.url}">${p.frontmatter.title}</a>${p.frontmatter.date ? ` — ${p.frontmatter.date}` : ""}</li>`
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
</head>
<body>
  <h1>${title}</h1>
  <ul>${items}</ul>
</body>
</html>`;
}

function copyStatic(templateDir: string, outputDir: string): void {
  const staticDir = path.join(templateDir, "static");
  if (!fs.existsSync(staticDir)) return;
  copyDirSync(staticDir, outputDir);
}

function copyDirSync(src: string, dest: string): void {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}
