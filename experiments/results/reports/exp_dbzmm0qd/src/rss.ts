import { Page, SiteConfig } from "./types.js";

export function generateRss(pages: Page[], config: SiteConfig): string {
  const posts = pages
    .filter((p) => !p.frontmatter.draft && p.frontmatter.date)
    .sort((a, b) => (b.frontmatter.date!.getTime() - a.frontmatter.date!.getTime()));

  const items = posts.map((p) => {
    const title = escapeXml(p.frontmatter.title);
    const link = `${config.siteUrl}/${p.url}`;
    const date = p.frontmatter.date!.toUTCString();
    const description = escapeXml(p.html.slice(0, 500));

    return `    <item>
      <title>${title}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${date}</pubDate>
      <description>${description}</description>
    </item>`;
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${config.siteUrl}</link>
    <description>${escapeXml(config.siteTitle)}</description>
    <atom:link href="${config.siteUrl}/rss.xml" rel="self" type="application/rss+xml"/>
${items.join("\n")}
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
