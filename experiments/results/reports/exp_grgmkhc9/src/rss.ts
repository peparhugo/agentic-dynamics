import { Page, SiteConfig } from "./types";

export function generateRss(pages: Page[], config: SiteConfig): string {
  const published = pages
    .filter((p) => !p.frontmatter.draft && p.frontmatter.date)
    .sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    });

  const items = published
    .map((page) => {
      const title = escapeXml(page.frontmatter.title ?? page.slug);
      const link = `${config.siteUrl}/${page.slug}`;
      const date = page.frontmatter.date
        ? new Date(page.frontmatter.date).toUTCString()
        : new Date().toUTCString();
      const description = escapeXml(page.content.slice(0, 300));

      return `    <item>
      <title>${title}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${date}</pubDate>
      <description>${description}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.siteTitle)}</title>
    <link>${config.siteUrl}</link>
    <description>${escapeXml(config.siteTitle)}</description>
    <atom:link href="${config.siteUrl}/rss.xml" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>
`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
