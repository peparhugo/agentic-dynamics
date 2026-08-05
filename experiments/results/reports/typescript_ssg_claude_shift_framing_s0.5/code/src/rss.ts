import type { Page, SiteConfig } from "./types.js";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Generate an RSS 2.0 feed for the newest `limit` dated pages. */
export function generateRss(pages: Page[], site: SiteConfig, limit = 20): string {
  const dated = pages
    .filter((p) => p.frontmatter.date !== null)
    .sort((a, b) => b.frontmatter.date!.getTime() - a.frontmatter.date!.getTime())
    .slice(0, limit);

  const items = dated
    .map((p) => {
      const link = site.url.replace(/\/$/, "") + p.url;
      return [
        "    <item>",
        `      <title>${esc(p.frontmatter.title)}</title>`,
        `      <link>${esc(link)}</link>`,
        `      <guid>${esc(link)}</guid>`,
        `      <pubDate>${p.frontmatter.date!.toUTCString()}</pubDate>`,
        `      <description>${esc(p.excerpt)}</description>`,
        "    </item>",
      ].join("\n");
    })
    .join("\n");

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<rss version="2.0">`,
    `  <channel>`,
    `    <title>${esc(site.title)}</title>`,
    `    <link>${esc(site.url)}</link>`,
    `    <description>${esc(site.description)}</description>`,
    `    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>`,
    items,
    `  </channel>`,
    `</rss>`,
    ``,
  ].join("\n");
}
