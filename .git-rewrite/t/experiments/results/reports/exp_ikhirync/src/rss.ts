import type { Page } from "./types.js";

export function generateRss(pages: Page[], siteUrl: string): string {
  const items = pages
    .filter((p) => !p.frontmatter.draft)
    .sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    })
    .slice(0, 20)
    .map((p) => {
      const title = escapeXml(p.frontmatter.title);
      const url = escapeXml(`${siteUrl.replace(/\/$/, "")}${p.url}`);
      const date = p.frontmatter.date
        ? new Date(p.frontmatter.date).toUTCString()
        : "";
      return `    <item>
      <title>${title}</title>
      <link>${url}</link>
      <guid>${url}</guid>
      ${date ? `<pubDate>${escapeXml(date)}</pubDate>` : ""}
      <description>${escapeXml(p.html.slice(0, 500))}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Site Feed</title>
    <link>${escapeXml(siteUrl)}</link>
    <description>Latest posts</description>
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
