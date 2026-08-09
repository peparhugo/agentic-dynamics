import type { Page, SiteConfig } from "./types.js";

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function absoluteUrl(base: string, url: string): string {
  return base.replace(/\/+$/, "") + url;
}

/** Generate an RSS 2.0 feed for the given pages (newest first). */
export function generateRss(config: SiteConfig, pages: Page[]): string {
  const sorted = [...pages].sort(
    (a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0)
  );
  const items = sorted
    .map((page) => {
      const link = absoluteUrl(config.siteUrl, page.url);
      const pubDate = page.frontmatter.date ? `\n      <pubDate>${page.frontmatter.date.toUTCString()}</pubDate>` : "";
      return `    <item>
      <title>${escapeXml(page.frontmatter.title)}</title>
      <link>${escapeXml(link)}</link>
      <guid>${escapeXml(link)}</guid>${pubDate}
      <description><![CDATA[${page.html}]]></description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(config.siteUrl)}</link>
    <description>${escapeXml(config.siteDescription)}</description>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}
