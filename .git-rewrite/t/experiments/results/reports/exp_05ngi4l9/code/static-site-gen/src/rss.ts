import type { SiteData } from "./types.js";
import { formatDate } from "./frontmatter.js";

export function rssXml(data: SiteData): string {
  const items = data.posts
    .slice(0, 20)
    .map(
      (p) => `    <item>
      <title>${esc(p.frontmatter.title)}</title>
      <link>${esc(data.site.url)}/${esc(p.slug)}.html</link>
      <description>${esc(p.excerpt ?? "")}</description>
      <pubDate>${p.frontmatter.date ? new Date(p.frontmatter.date).toUTCString() : ""}</pubDate>
      <guid>${esc(data.site.url)}/${esc(p.slug)}.html</guid>
    </item>`
    )
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${esc(data.site.title)}</title>
    <description>${esc(data.site.description)}</description>
    <link>${esc(data.site.url)}</link>
    <atom:link href="${esc(data.site.url)}/feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>`;
}

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
