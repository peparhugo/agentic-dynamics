import type { Page, SiteConfig } from "./types.js";

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function absUrl(baseUrl: string, url: string): string {
  return baseUrl.replace(/\/$/, "") + url;
}

/** Generate an RSS 2.0 feed for the given pages (assumed already sorted, drafts excluded). */
export function generateRss(pages: Page[], config: SiteConfig, limit = 20): string {
  const items = pages.slice(0, limit).map((page) => {
    const link = absUrl(config.baseUrl, page.url);
    const pubDate = page.frontmatter.date ? page.frontmatter.date.toUTCString() : "";
    return [
      "    <item>",
      `      <title>${escapeXml(page.frontmatter.title)}</title>`,
      `      <link>${escapeXml(link)}</link>`,
      `      <guid>${escapeXml(link)}</guid>`,
      pubDate ? `      <pubDate>${pubDate}</pubDate>` : "",
      page.frontmatter.tags.map((t) => `      <category>${escapeXml(t)}</category>`).join("\n"),
      `      <description><![CDATA[${page.html}]]></description>`,
      "    </item>",
    ]
      .filter(Boolean)
      .join("\n");
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(config.baseUrl)}</link>
    <description>${escapeXml(config.siteDescription)}</description>
    <atom:link href="${escapeXml(absUrl(config.baseUrl, "/feed.xml"))}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items.join("\n")}
  </channel>
</rss>
`;
}
