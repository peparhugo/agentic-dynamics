import { Post, SiteConfig } from "./types";

export interface RssItem {
  title: string;
  description: string;
  url: string;
  date: string;
}

export function generateRssXml(
  config: SiteConfig,
  posts: Post[]
): string {
  const items = posts.map((p) => rssItem(config, p));
  return [
    `<?xml version="1.0" encoding="utf-8"?>`,
    `<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">`,
    `<channel>`,
    `<title>${escapeXml(config.title)}</title>`,
    `<link>${escapeXml(config.url)}</link>`,
    `<description>${escapeXml(config.description)}</description>`,
    `<atom:link href="${escapeXml(config.url)}/feed.xml" rel="self" type="application/rss+xml"/>`,
    ...items.map((item) => [
      `<item>`,
      `<title>${escapeXml(item.title)}</title>`,
      `<link>${escapeXml(item.url)}</link>`,
      `<description>${escapeXml(item.description)}</description>`,
      `<pubDate>${new Date(item.date).toUTCString()}</pubDate>`,
      `<guid>${escapeXml(item.url)}</guid>`,
      `</item>`,
    ].join("\n")),
    `</channel>`,
    `</rss>`,
  ].join("\n");
}

function rssItem(config: SiteConfig, post: Post): RssItem {
  return {
    title: post.title,
    description: post.excerpt,
    url: `${config.url}/${post.slug}.html`,
    date: post.date,
  };
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
