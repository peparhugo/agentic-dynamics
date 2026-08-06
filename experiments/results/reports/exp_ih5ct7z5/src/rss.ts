import fs from "fs";
import path from "path";
import { Post, SiteConfig } from "./types";

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function generateRssFeed(posts: Post[], config: SiteConfig): string {
  const items = posts
    .filter((p) => !p.frontmatter.draft)
    .map((p) => {
      const date = p.frontmatter.date || new Date().toISOString();
      const url = new URL(p.url, config.baseUrl).href;
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid isPermaLink="true">${escapeXml(url)}</guid>
      <pubDate>${new Date(date).toUTCString()}</pubDate>
      <description>${escapeXml(p.html.substring(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.title)}</title>
    <description>${escapeXml(config.description)}</description>
    <link>${escapeXml(config.baseUrl)}</link>
    <atom:link href="${escapeXml(new URL("/rss.xml", config.baseUrl).href)}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>`;
}

export function writeRssFeed(outputDir: string, posts: Post[], config: SiteConfig): void {
  const rss = generateRssFeed(posts, config);
  const rssPath = path.join(outputDir, "rss.xml");
  fs.mkdirSync(path.dirname(rssPath), { recursive: true });
  fs.writeFileSync(rssPath, rss, "utf-8");
}
