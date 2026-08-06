import { Page, SiteConfig } from "./types";

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function generateRSS(
  pages: Page[],
  siteConfig: SiteConfig,
  baseUrl: string
): string {
  const items = pages
    .filter((p) => !p.frontmatter.draft && p.frontmatter.date)
    .sort((a, b) => {
      const dateA = new Date(a.frontmatter.date!).getTime();
      const dateB = new Date(b.frontmatter.date!).getTime();
      return dateB - dateA;
    })
    .slice(0, 20)
    .map((p) => {
      const url = baseUrl.replace(/\/$/, "") + p.url;
      const date = new Date(p.frontmatter.date!);
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid isPermaLink="true">${escapeXml(url)}</guid>
      <pubDate>${date.toUTCString()}</pubDate>
      <description>${escapeXml(p.html.slice(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  const now = new Date().toUTCString();

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteConfig.title)}</title>
    <description>${escapeXml(siteConfig.description)}</description>
    <link>${escapeXml(baseUrl)}</link>
    <atom:link href="${escapeXml(baseUrl.replace(/\/$/, "") + "/feed.xml")}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${now}</lastBuildDate>
${items}
  </channel>
</rss>`;
}
