import { Page, SSGConfig } from "./types.js";

export function generateRssXml(config: SSGConfig, pages: Page[]): string {
  const published = pages
    .filter((p) => !p.frontmatter.draft && p.frontmatter.date)
    .sort(
      (a, b) =>
        (b.frontmatter.date?.getTime() ?? 0) -
        (a.frontmatter.date?.getTime() ?? 0)
    )
    .slice(0, 20);

  const items = published
    .map((p) => {
      const date = p.frontmatter.date!;
      const rfc822 = date.toUTCString();
      const url = `${config.siteUrl}/${p.slug}.html`;
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid>${escapeXml(url)}</guid>
      <pubDate>${rfc822}</pubDate>
      <description>${escapeXml(p.html.slice(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${escapeXml(config.siteUrl)}</link>
    <description>${escapeXml(config.siteDescription)}</description>
    <atom:link href="${escapeXml(config.siteUrl)}/rss.xml" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
