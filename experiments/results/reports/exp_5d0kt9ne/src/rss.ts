import { Feed } from "feed";
import { Page, SiteConfig } from "./types";
import path from "path";

export function generateRss(pages: Page[], config: SiteConfig): string {
  const published = pages.filter(p => !p.frontmatter.draft && p.frontmatter.date);
  published.sort((a, b) => new Date(b.frontmatter.date!).getTime() - new Date(a.frontmatter.date!).getTime());

  const feed = new Feed({
    title: config.siteName,
    description: config.siteName,
    id: config.siteUrl,
    link: config.siteUrl,
    language: "en",
    updated: published.length > 0 ? new Date(published[0].frontmatter.date!) : new Date(),
    copyright: `All rights reserved ${new Date().getFullYear()}`,
    author: config.author ? { name: config.author } : undefined,
  });

  for (const p of published.slice(0, 50)) {
    feed.addItem({
      title: p.frontmatter.title || path.basename(p.sourcePath, ".md"),
      id: config.siteUrl.replace(/\/$/, "") + p.path,
      link: config.siteUrl.replace(/\/$/, "") + p.path,
      date: new Date(p.frontmatter.date!),
      content: p.html,
    });
  }

  return feed.rss2();
}
