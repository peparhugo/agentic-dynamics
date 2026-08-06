import type { Page, SiteConfig } from "./types.js";

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function generateRSS(pages: Page[], config: SiteConfig): string {
  const items = pages
    .filter((p) => p.frontmatter.date)
    .sort((a, b) => new Date(b.frontmatter.date!).getTime() - new Date(a.frontmatter.date!).getTime())
    .map((p) => {
      const url = config.baseUrl.replace(/\/$/, "") + p.url;
      const dateStr = new Date(p.frontmatter.date!).toUTCString();
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid isPermaLink="true">${escapeXml(url)}</guid>
      <pubDate>${dateStr}</pubDate>
      <description>${escapeXml(p.html.slice(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  const lastBuild = new Date().toUTCString();
  const baseUrl = config.baseUrl.replace(/\/$/, "");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(baseUrl)}</link>
    <description>${escapeXml(config.siteDescription)}</description>
    <lastBuildDate>${lastBuild}</lastBuildDate>
    <atom:link href="${escapeXml(baseUrl + "/rss.xml")}" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>`;
}
