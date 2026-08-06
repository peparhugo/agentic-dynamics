import fs from "node:fs/promises";
import path from "node:path";
import { Feed } from "feed";
import type { Page, SiteConfig } from "./types.js";
import { parseDate } from "./parser.js";

export async function generateRss(config: SiteConfig, pages: Page[]): Promise<void> {
  const feed = new Feed({
    title: config.siteTitle,
    description: `${config.siteTitle} RSS feed`,
    id: config.siteUrl,
    link: config.siteUrl,
    language: "en",
    updated: new Date(),
    generator: "staticsmith",
    feedLinks: {
      rss2: `${config.siteUrl}/feed.xml`,
    },
    copyright: "",
  });

  const publishedPages = pages
    .filter((p) => parseDate(p.frontmatter.date) !== undefined)
    .sort((a, b) => {
      const da = parseDate(a.frontmatter.date)!;
      const db = parseDate(b.frontmatter.date)!;
      return db.getTime() - da.getTime();
    });

  for (const page of publishedPages) {
    feed.addItem({
      title: page.frontmatter.title,
      id: config.siteUrl + page.url,
      link: config.siteUrl + page.url,
      date: parseDate(page.frontmatter.date)!,
      description: page.html,
      content: page.html,
    });
  }

  const outPath = path.join(config.outputDir, "feed.xml");
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, feed.rss2(), "utf-8");
}
