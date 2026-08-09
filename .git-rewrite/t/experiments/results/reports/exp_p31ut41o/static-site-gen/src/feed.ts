import type { Site, Page } from "./types.js";

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function rssItem(post: Page, site: Site): string {
  const title = escapeXml(post.frontmatter.title || "Untitled");
  const link = escapeXml(`${site.config.siteUrl}${post.url}`);
  let date = "";
  if (post.frontmatter.date) {
    date = `<pubDate>${new Date(post.frontmatter.date).toUTCString()}</pubDate>`;
  }
  const description = escapeXml(post.content.slice(0, 300) + "...");
  return `    <item>
      <title>${title}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      ${date}
      <description>${description}</description>
    </item>`;
}

export function generateRSS(site: Site): string {
  const title = escapeXml(site.config.siteTitle);
  const link = escapeXml(site.config.siteUrl);
  const desc = escapeXml(site.config.siteDescription || "");
  const items = site.posts.map((p) => rssItem(p, site)).join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${title}</title>
    <link>${link}</link>
    <description>${desc}</description>
    <language>en-us</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${link}/rss.xml" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>`;
}
