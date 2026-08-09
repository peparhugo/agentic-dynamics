import fs from "fs";
import path from "path";
import { Post, SiteConfig } from "./types";
import { TemplateContext, renderPage } from "./renderer";
import Handlebars from "handlebars";

export function buildTagIndex(
  posts: Post[]
): { tags: Record<string, Post[]>; tagList: Array<{ name: string; count: number }> } {
  const tags: Record<string, Post[]> = {};

  for (const post of posts) {
    if (post.frontmatter.draft) continue;
    for (const tag of post.frontmatter.tags) {
      if (!tags[tag]) tags[tag] = [];
      tags[tag].push(post);
    }
  }

  const tagList = Object.entries(tags)
    .map(([name, tagPosts]) => ({ name, count: tagPosts.length }))
    .sort((a, b) => b.count - a.count);

  return { tags, tagList };
}

export function generateTagPages(
  tags: Record<string, Post[]>,
  tagList: Array<{ name: string; count: number }>,
  templates: Record<string, Handlebars.TemplateDelegate>,
  layouts: Record<string, Handlebars.TemplateDelegate>,
  outputDir: string,
  allPosts: Post[],
  config: SiteConfig
): void {
  const tagDir = path.join(outputDir, "tags");
  fs.mkdirSync(tagDir, { recursive: true });

  for (const [tag, tagPosts] of Object.entries(tags)) {
    const context: TemplateContext = {
      content: "",
      title: `Posts tagged "${tag}"`,
      tags: [tag],
      url: `/tags/${encodeURIComponent(tag)}.html`,
      site: {
        ...config,
        posts: tagPosts,
        tags: tagList,
      },
    };

    let html: string;
    if (templates.tag) {
      html = renderPage("tag", templates, layouts, context);
    } else if (templates.index) {
      html = renderPage("index", templates, layouts, context);
    } else {
      html = buildDefaultTagPage(tag, tagPosts, config);
    }

    const filePath = path.join(tagDir, `${encodeURIComponent(tag)}.html`);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, html, "utf-8");
  }
}

function buildDefaultTagPage(tag: string, posts: Post[], config: SiteConfig): string {
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
  <title>Posts tagged "${tag}" — ${config.title}</title>
</head>
<body>
  <h1>Posts tagged "${tag}"</h1>
  <ul>${items}</ul>
  <p><a href="/">← Back to home</a></p>
</body>
</html>`;
}
