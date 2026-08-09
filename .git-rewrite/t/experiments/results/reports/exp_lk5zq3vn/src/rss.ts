import type { Page, SiteConfig } from "./types.js";

export function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Generate an RSS 2.0 feed for the given pages (newest first, max 20). */
export function generateRss(pages: Page[], config: SiteConfig): string {
  const base = config.baseUrl.replace(/\/$/, "");
  const items = [...pages]
    .filter((p) => p.frontmatter.date)
    .sort((a, b) => b.frontmatter.date!.getTime() - a.frontmatter.date!.getTime())
    .slice(0, 20)
    .map((p) => {
      const link = `${base}${p.urlPath}`;
      return [
        "    <item>",
        `      <title>${escapeXml(p.frontmatter.title)}</title>`,
        `      <link>${escapeXml(link)}</link>`,
        `      <guid>${escapeXml(link)}</guid>`,
        `      <pubDate>${p.frontmatter.date!.toUTCString()}</pubDate>`,
        `      <description>${escapeXml(p.html)}</description>`,
        "    </item>",
      ].join("\n");
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(base)}</link>
    <description>${escapeXml(config.siteDescription)}</description>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}
