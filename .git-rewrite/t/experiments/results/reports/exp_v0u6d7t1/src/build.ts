import fs from "node:fs/promises";
import path from "node:path";
import type { BuildContext, CLIOptions, Page } from "./types.js";
import { discoverMarkdownFiles, createPage } from "./frontmatter.js";
import { markdownToHtml } from "./markdown.js";
import { createTemplateEngine } from "./templates.js";
import { generateRssFeed } from "./rss.js";
import { generateTagPages } from "./tags.js";

export async function build(opts: CLIOptions): Promise<BuildContext> {
  const files = await discoverMarkdownFiles(opts.source);
  const engine = await createTemplateEngine(opts.templates);

  const pages: Page[] = [];
  for (const file of files) {
    const raw = await fs.readFile(file, "utf-8");
    const page = createPage(file, opts.source, opts.output, raw);
    page.html = markdownToHtml(page.content);
    pages.push(page);
  }

  const publishedPages = pages.filter((p) => !p.isDraft);
  publishedPages.sort((a, b) => {
    if (!a.frontmatter.date) return 1;
    if (!b.frontmatter.date) return -1;
    return new Date(b.frontmatter.date!).getTime() -
      new Date(a.frontmatter.date!).getTime();
  });

  const tagMap = buildTagMap(publishedPages);

  const ctx: BuildContext = {
    pages,
    publishedPages,
    tagMap,
    siteTitle: opts.siteTitle,
    siteUrl: opts.siteUrl,
  };

  await fs.rm(opts.output, { recursive: true, force: true });
  await fs.mkdir(opts.output, { recursive: true });

  const globalContext = {
    site: {
      title: opts.siteTitle,
      url: opts.siteUrl,
      pages: publishedPages.map((p) => ({
        title: p.frontmatter.title,
        url: p.url,
        date: p.frontmatter.date,
        tags: p.tags,
      })),
    },
  };

  for (const page of pages) {
    const html = await engine.render(page, page.html, {
      ...globalContext,
      pages: publishedPages.filter((p) => p !== page).map((p) => ({
        title: p.frontmatter.title,
        url: p.url,
        date: p.frontmatter.date,
        tags: p.tags,
      })),
    });
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, html);
  }

  // Generate tag index pages
  const tagPages = await generateTagPages(ctx, opts.templates);
  for (const [tag, html] of tagPages) {
    const tagDir = path.join(opts.output, "tags", tag);
    await fs.mkdir(tagDir, { recursive: true });
    await fs.writeFile(path.join(tagDir, "index.html"), html);
  }

  // Generate RSS feed
  const rss = await generateRssFeed(ctx, opts.templates);
  await fs.writeFile(path.join(opts.output, "feed.xml"), rss);

  // Generate tag listing page
  if (ctx.tagMap.size > 0) {
    const tagsListHtml = generateTagsListing(ctx);
    const tagsDir = path.join(opts.output, "tags");
    await fs.mkdir(tagsDir, { recursive: true });
    await fs.writeFile(path.join(tagsDir, "index.html"), tagsListHtml);
  }

  return ctx;
}

function buildTagMap(pages: Page[]): Map<string, Page[]> {
  const map = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.tags) {
      if (!map.has(tag)) map.set(tag, []);
      map.get(tag)!.push(page);
    }
  }
  return map;
}

function generateTagsListing(ctx: BuildContext): string {
  const tags = [...ctx.tagMap.entries()]
    .sort(([a], [b]) => a.localeCompare(b));

  const items = tags.map(([tag, pages]) =>
    `<li><a href="/tags/${tag}/">${tag}</a> (${pages.length})</li>`,
  ).join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${ctx.siteTitle} - Tags</title>
</head>
<body>
  <h1>Tags</h1>
  <ul>${items}</ul>
</body>
</html>`;
}
