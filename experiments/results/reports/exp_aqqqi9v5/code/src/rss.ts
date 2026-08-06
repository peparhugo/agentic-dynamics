import type { Page, SiteConfig } from "./types.js";

export function generateRSS(pages: Page[], config: SiteConfig): string {
  const published = pages
    .filter((p) => !p.isDraft)
    .sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    });

  const items = published
    .slice(0, 20)
    .map((p) => {
      const link = `${config.baseUrl.replace(/\/$/, "")}/${p.slug}.html`;
      const date = p.frontmatter.date
        ? new Date(p.frontmatter.date).toUTCString()
        : new Date().toUTCString();
      const tags = (p.frontmatter.tags ?? [])
        .map((t) => `<category>${escapeXML(t)}</category>`)
        .join("\n      ");

      return `    <item>
      <title>${escapeXML(p.frontmatter.title)}</title>
      <link>${escapeXML(link)}</link>
      <guid isPermaLink="true">${escapeXML(link)}</guid>
      <pubDate>${date}</pubDate>
      ${tags}
      <description>${escapeXML(p.html.slice(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXML(config.title)}</title>
    <description>${escapeXML(config.description)}</description>
    <link>${escapeXML(config.baseUrl)}</link>
    <atom:link href="${escapeXML(config.baseUrl)}/rss.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>`;
}

function escapeXML(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
