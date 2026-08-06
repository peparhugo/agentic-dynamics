import type { Frontmatter } from "./frontmatter.js";

interface RSSOptions {
  title: string;
  description: string;
  siteUrl: string;
  posts: Frontmatter[];
}

export function generateRSS(opts: RSSOptions): string {
  const { title, description, siteUrl, posts } = opts;
  const items = posts
    .filter((p) => !p.draft)
    .map((p) => {
      const url = `${siteUrl}/${p.slug || ""}`;
      return `<item>
      <title><![CDATA[${escapeXML(p.title)}]]></title>
      <link>${escapeXML(url)}</link>
      <guid isPermaLink="true">${escapeXML(url)}</guid>
      <pubDate>${p.date ? new Date(p.date).toUTCString() : ""}</pubDate>
      ${(p.tags ?? []).map((t) => `<category>${escapeXML(t)}</category>`).join("\n      ")}
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXML(title)}</title>
    <description>${escapeXML(description)}</description>
    <link>${escapeXML(siteUrl)}</link>
    <atom:link href="${escapeXML(siteUrl)}/feed.xml" rel="self" type="application/rss+xml"/>
    ${items}
  </channel>
</rss>`;
}

function escapeXML(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
