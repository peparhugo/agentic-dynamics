import { Feed } from "feed";
import * as fs from "fs";
import * as path from "path";
import { Page } from "./types";

export function generateRss(pages: Page[], siteTitle: string, siteUrl: string, outputDir: string, feedPath?: string): void {
  const feed = new Feed({
    title: siteTitle,
    description: `Latest posts from ${siteTitle}`,
    id: siteUrl,
    link: siteUrl,
    language: "en",
    updated: new Date(),
    generator: "triton",
    copyright: "",
    feedLinks: {
      rss2: `${siteUrl}/rss.xml`,
    },
  });

  for (const page of pages) {
    feed.addItem({
      title: page.frontmatter.title,
      id: `${siteUrl}${page.url}`,
      link: `${siteUrl}${page.url}`,
      description: page.html.substring(0, 500),
      content: page.html,
      date: page.frontmatter.date ?? new Date(),
    });
  }

  const outputPath = path.join(outputDir, feedPath ?? "rss.xml");
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, feed.rss2());
}
