import type { Post } from "./content.js";
import { escapeHtml } from "./content.js";

export interface RssOptions {
  title: string;
  description: string;
  baseUrl: string;
  limit?: number;
}

/** Generate an RSS 2.0 feed for the given posts (assumed sorted newest first). */
export function generateRss(posts: Post[], opts: RssOptions): string {
  const base = opts.baseUrl.replace(/\/$/, "");
  const items = posts.slice(0, opts.limit ?? 20).map((p) => {
    const link = `${base}${p.url}`;
    return [
      "    <item>",
      `      <title>${escapeHtml(p.title)}</title>`,
      `      <link>${escapeHtml(link)}</link>`,
      `      <guid isPermaLink="true">${escapeHtml(link)}</guid>`,
      `      <pubDate>${p.date.toUTCString()}</pubDate>`,
      ...p.tags.map((t) => `      <category>${escapeHtml(t)}</category>`),
      `      <description><![CDATA[${p.html.replace(/\]\]>/g, "]]]]><![CDATA[>")}]]></description>`,
      "    </item>",
    ].join("\n");
  });

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<rss version="2.0">`,
    `  <channel>`,
    `    <title>${escapeHtml(opts.title)}</title>`,
    `    <link>${escapeHtml(base + "/")}</link>`,
    `    <description>${escapeHtml(opts.description)}</description>`,
    `    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>`,
    ...items,
    `  </channel>`,
    `</rss>`,
    ``,
  ].join("\n");
}
