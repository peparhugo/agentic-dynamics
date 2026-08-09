import type { Page, SiteConfig } from "./types.js";
import { parseDate } from "./frontmatter.js";

export function generateRss(pages: Page[], config: SiteConfig): string {
  const publishable = pages
    .filter((p) => !p.isDraft)
    .sort((a, b) => {
      return (
        (parseDate(b.frontmatter)?.getTime() ?? 0) -
        (parseDate(a.frontmatter)?.getTime() ?? 0)
      );
    });

  const items = publishable
    .map((page) => {
      const date = parseDate(page.frontmatter);
      const rfcDate = date ? date.toUTCString() : new Date().toUTCString();
      return `    <item>
      <title>${escapeXml(page.frontmatter.title)}</title>
      <link>${config.siteUrl}${page.url}</link>
      <guid>${config.siteUrl}${page.url}</guid>
      <pubDate>${rfcDate}</pubDate>
      <description>${escapeXml(page.content.slice(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${config.siteUrl}</link>
    <description>${escapeXml(config.siteTitle)} RSS Feed</description>
    <atom:link href="${config.siteUrl}/rss.xml" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>`;
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
