import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Page, SiteConfig } from "./types.js";

function escapeXml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function rfc822Date(d: string): string {
  return new Date(d).toUTCString();
}

export async function generateRss(pages: Page[], config: SiteConfig): Promise<void> {
  const items = pages
    .filter((p) => !p.frontmatter.draft)
    .sort((a, b) => {
      const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
      const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
      return db - da;
    })
    .slice(0, 20)
    .map((p) => {
      const url = `${config.baseUrl}/${p.slug}.html`;
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid isPermaLink="true">${escapeXml(url)}</guid>
      <description>${escapeXml(p.html.slice(0, 300))}</description>
      ${p.frontmatter.date ? `<pubDate>${rfc822Date(p.frontmatter.date)}</pubDate>` : ""}
      <content:encoded><![CDATA[${p.html}]]></content:encoded>
    </item>`;
    })
    .join("\n");

  const feed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.title)}</title>
    <link>${escapeXml(config.baseUrl)}</link>
    <description>${escapeXml(config.description)}</description>
    <atom:link href="${escapeXml(config.baseUrl)}/rss.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${rfc822Date(new Date().toISOString())}</lastBuildDate>
${items}
  </channel>
</rss>`;

  await writeFile(join(config.out, "rss.xml"), feed, "utf-8");
}
