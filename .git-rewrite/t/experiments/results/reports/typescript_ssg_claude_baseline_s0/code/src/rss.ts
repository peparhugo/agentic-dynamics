import type { Page, SiteConfig } from "./types.js";

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function absoluteUrl(baseUrl: string, url: string): string {
  return `${baseUrl.replace(/\/+$/, "")}${url}`;
}

/** Generate an RSS 2.0 feed for dated, non-draft pages (newest first, max `limit`). */
export function generateRss(
  pages: Page[],
  site: SiteConfig,
  limit = 20
): string {
  const items = pages
    .filter((p) => !p.meta.draft && p.meta.date !== null)
    .sort((a, b) => (b.meta.date?.getTime() ?? 0) - (a.meta.date?.getTime() ?? 0))
    .slice(0, limit)
    .map((p) => {
      const link = absoluteUrl(site.baseUrl, p.url);
      return [
        "    <item>",
        `      <title>${escapeXml(p.meta.title)}</title>`,
        `      <link>${escapeXml(link)}</link>`,
        `      <guid>${escapeXml(link)}</guid>`,
        `      <pubDate>${p.meta.date!.toUTCString()}</pubDate>`,
        p.meta.tags.map((t) => `      <category>${escapeXml(t)}</category>`).join("\n"),
        `      <description><![CDATA[${p.html.replace(/]]>/g, "]]&gt;")}]]></description>`,
        "    </item>",
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(site.title)}</title>
    <link>${escapeXml(site.baseUrl)}</link>
    <description>${escapeXml(site.description)}</description>
    <atom:link href="${escapeXml(absoluteUrl(site.baseUrl, "/feed.xml"))}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}
