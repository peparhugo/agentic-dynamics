import RSS from "rss";
import type { Page, SiteConfig } from "../types";

export function buildRssFeed(
  pages: Page[],
  site: SiteConfig
): string {
  const feed = new RSS({
    title: site.title,
    description: site.description,
    feed_url: `${site.url}/feed.xml`,
    site_url: site.url,
    language: site.language || "en",
  });

  for (const page of pages) {
    if (page.frontmatter.draft) continue;
    feed.item({
      title: page.frontmatter.title,
      description: page.html,
      url: `${site.url}/${page.slug}.html`,
      date: page.frontmatter.date || new Date().toISOString(),
      categories: page.frontmatter.tags || [],
    });
  }

  return feed.xml({ indent: true });
}
