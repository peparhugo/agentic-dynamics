import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Post } from "./types.js";

export function generateRss(
  posts: Post[],
  outputDir: string,
  baseUrl: string,
  siteTitle: string,
  siteDescription: string
): void {
  const now = new Date().toUTCString();

  const items = posts
    .filter((p) => p.date)
    .map(
      (p) => `    <item>
      <title><![CDATA[${p.title}]]></title>
      <link>${baseUrl}${p.slug}/</link>
      <guid>${baseUrl}${p.slug}/</guid>
      <pubDate>${p.date!.toUTCString()}</pubDate>
      <description><![CDATA[${p.content.slice(0, 300)}]]></description>
    </item>`
    )
    .join("\n");

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${siteTitle}</title>
    <link>${baseUrl}</link>
    <description>${siteDescription}</description>
    <language>en</language>
    <lastBuildDate>${now}</lastBuildDate>
    <atom:link href="${baseUrl}rss.xml" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>`;

  writeFileSync(join(outputDir, "rss.xml"), rss);
}
