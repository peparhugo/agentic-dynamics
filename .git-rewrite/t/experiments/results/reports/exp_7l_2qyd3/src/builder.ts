import { compileLayout, compileTemplate, loadPartials, renderPage } from "./renderer.js";
import { buildTagIndex, generateTagPages } from "./tags.js";
import { generateRSS } from "./rss.js";
import { getPublishedPages, parseMarkdown, sortByDate } from "./parser.js";
import type { Page } from "./types.js";
import { copyFile, walkDir, writeTextFile, readTextFile } from "./utils.js";
import path from "node:path";
import fs from "node:fs";

export interface BuildOptions {
  source: string;
  templates: string;
  output: string;
  baseUrl: string;
  siteTitle: string;
  siteDescription: string;
  author?: string;
  includeDrafts: boolean;
}

export function build(options: BuildOptions): Page[] {
  const pages: Page[] = [];

  walkDir(options.source, (fpath, relative) => {
    if (!fpath.endsWith(".md")) return;
    const raw = readTextFile(fpath);
    const parsed = parseMarkdown(raw, relative);
    pages.push({
      ...parsed,
      outputPath: path.join(options.output, parsed.slug, "index.html"),
      html: "",
    });
  });

  const visible = options.includeDrafts ? pages : getPublishedPages(pages);
  const sorted = sortByDate(visible);

  loadPartials(path.join(options.templates, "partials"));

  const layout = compileLayout(options.templates, "layout");
  const pageTemplate = compileTemplate(options.templates, "page");
  const tagTemplate = compileTemplate(options.templates, "tag");
  const listingTemplate = compileTemplate(options.templates, "listing");

  const tags = buildTagIndex(sorted);

  const tagList = Array.from(tags.values()).map((t) => ({
    tag: t.tag,
    count: t.count,
  }));

  const siteContext = {
    title: options.siteTitle,
    description: options.siteDescription,
    baseUrl: options.baseUrl,
  };

  for (const page of sorted) {
    const ctx = {
      page: {
        ...page.frontmatter,
        content: page.content,
        slug: page.slug,
      },
      pages: sorted.map((p) => ({
        title: p.frontmatter.title,
        slug: p.slug,
        date: p.frontmatter.date,
        tags: p.frontmatter.tags,
      })),
      tags: tagList,
      site: siteContext,
    };
    page.html = renderPage(page.content, layout, pageTemplate, ctx);
    writeTextFile(page.outputPath, page.html);
  }

  const listingCtx = {
    pages: sorted.map((p) => ({
      title: p.frontmatter.title,
      slug: p.slug,
      date: p.frontmatter.date,
      tags: p.frontmatter.tags,
      content: p.content,
    })),
    tags: tagList,
    site: siteContext,
  };
  const listingHtml = renderPage("", layout, listingTemplate, listingCtx);
  writeTextFile(path.join(options.output, "index.html"), listingHtml);

  const tagPages = generateTagPages(tags, sorted, (tagInfo, allPages) => {
    const ctx = {
      tag: { tag: tagInfo.tag, count: tagInfo.count },
      pages: tagInfo.pages.map((p) => ({
        title: p.frontmatter.title,
        slug: p.slug,
        date: p.frontmatter.date,
        tags: p.frontmatter.tags,
      })),
      tags: tagList,
      site: siteContext,
    };
    if (layout) {
      return layout({ ...ctx, body: tagTemplate(ctx) });
    }
    return tagTemplate(ctx);
  });

  for (const [relPath, html] of tagPages) {
    writeTextFile(path.join(options.output, relPath), html);
  }

  const rssXml = generateRSS(sorted, {
    title: options.siteTitle,
    description: options.siteDescription,
    baseUrl: options.baseUrl,
    author: options.author,
  });
  writeTextFile(path.join(options.output, "feed.xml"), rssXml);

  walkDir(options.source, (fpath, relative) => {
    if (fpath.endsWith(".md")) return;
    copyFile(fpath, path.join(options.output, relative));
  });

  walkDir(options.templates, (fpath, relative) => {
    if (fpath.endsWith(".hbs")) return;
    copyFile(fpath, path.join(options.output, relative));
  });

  return sorted;
}
