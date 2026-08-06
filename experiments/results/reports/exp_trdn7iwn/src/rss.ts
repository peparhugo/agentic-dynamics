import type { Page } from "./build.js";

export interface RssOptions {
  title: string;
  description: string;
  siteUrl: string;
}

const escapeXml = (s: string): string =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");

/** Generate an RSS 2.0 feed from published (non-draft) pages, newest first. */
export function generateRss(pages: Page[], opts: RssOptions): string {
  const base = opts.siteUrl.replace(/\/+$/, "");
  const items = pages
    .filter((p) => !p.frontmatter.draft)
    .sort((a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0))
    .map((p) => {
      const url = `${base}${p.url}`;
      const pubDate = p.frontmatter.date ? `\n      <pubDate>${p.frontmatter.date.toUTCString()}</pubDate>` : "";
      return `    <item>
      <title>${escapeXml(p.frontmatter.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid>${escapeXml(url)}</guid>${pubDate}
      <description>${escapeXml(p.html)}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${escapeXml(opts.title)}</title>
    <link>${escapeXml(base)}</link>
    <description>${escapeXml(opts.description)}</description>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}
