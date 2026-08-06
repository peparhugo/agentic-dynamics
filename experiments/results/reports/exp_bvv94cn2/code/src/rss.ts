import type { Page, SiteConfig } from "./types.js";
import { formatDate, parseDate } from "./utils.js";

function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function generateRss(pages: Page[], config: SiteConfig): string {
  const published = pages
    .filter(p => !p.frontmatter.draft && p.frontmatter.date)
    .sort((a, b) => {
      const da = parseDate(a.frontmatter.date!);
      const db = parseDate(b.frontmatter.date!);
      return db.getTime() - da.getTime();
    })
    .slice(0, 20);

  const items = published
    .map(p => {
      const date = parseDate(p.frontmatter.date!);
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(config.siteUrl + p.url)}</link>
      <guid>${escapeXml(config.siteUrl + p.url)}</guid>
      <pubDate>${date.toUTCString()}</pubDate>
      <description>${escapeXml(p.frontmatter.title)}</description>
    </item>`;
    })
    .join("\n");

  const now = new Date().toUTCString();

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(config.siteUrl)}</link>
    <description>${escapeXml(config.siteTitle)}</description>
    <language>en</language>
    <lastBuildDate>${now}</lastBuildDate>
    <atom:link href="${escapeXml(config.siteUrl + "/feed.xml")}" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>
`;
}
