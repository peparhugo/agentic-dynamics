import { Feed } from "feed";
import type { Page } from "./types.js";

export interface RSSOptions {
  title: string;
  description: string;
  baseUrl: string;
  author?: string;
}

export function generateRSS(pages: Page[], options: RSSOptions): string {
  const feed = new Feed({
    title: options.title,
    description: options.description,
    id: options.baseUrl,
    link: options.baseUrl,
    language: "en",
    updated: pages.length > 0 ? new Date(pages[0].frontmatter.date ?? Date.now()) : new Date(),
    copyright: "",
    author: {
      name: options.author ?? options.title,
    },
  });

  for (const page of pages) {
    const url = `${options.baseUrl}/${page.slug}/`;
    feed.addItem({
      title: page.frontmatter.title,
      id: url,
      link: url,
      description: page.content,
      date: new Date(page.frontmatter.date ?? Date.now()),
    });
  }

  return feed.rss2();
}
