import { Page, SiteConfig } from "./types";
import { Feed } from "feed";

export function generateRSS(pages: Page[], config: SiteConfig): string {
  const published = pages.filter((p) => !p.meta.draft && p.meta.date);

  const feed = new Feed({
    title: config.siteTitle,
    description: config.siteDescription,
    id: config.siteUrl,
    link: config.siteUrl,
    language: "en",
    updated: published.length > 0 ? published[0].meta.date : new Date(),
    generator: "static-site-gen",
    copyright: "",
    feedLinks: {
      rss2: `${config.siteUrl}/rss.xml`,
    },
  });

  for (const page of published) {
    feed.addItem({
      title: page.meta.title,
      id: `${config.siteUrl}${page.url}`,
      link: `${config.siteUrl}${page.url}`,
      description: page.content.substring(0, 500),
      date: page.meta.date!,
    });
  }

  return feed.rss2();
}
