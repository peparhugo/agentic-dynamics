import type { Page } from "./build.js";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export interface RssOptions {
  title: string;
  url: string; // site base URL, no trailing slash required
  description?: string;
  limit?: number;
}

/** Generate an RSS 2.0 feed from pages (drafts already excluded). */
export function generateRss(pages: Page[], opts: RssOptions): string {
  const base = opts.url.replace(/\/+$/, "");
  const items = [...pages]
    .sort((a, b) => (b.data.date?.getTime() ?? 0) - (a.data.date?.getTime() ?? 0))
    .slice(0, opts.limit ?? 20)
    .map((p) => {
      const link = `${base}${p.urlPath}`;
      const date = p.data.date ? `<pubDate>${p.data.date.toUTCString()}</pubDate>` : "";
      const cats = p.data.tags.map((t) => `<category>${esc(t)}</category>`).join("");
      return [
        "    <item>",
        `      <title>${esc(p.data.title)}</title>`,
        `      <link>${esc(link)}</link>`,
        `      <guid isPermaLink="true">${esc(link)}</guid>`,
        date ? `      ${date}` : "",
        cats ? `      ${cats}` : "",
        `      <description>${esc(p.html)}</description>`,
        "    </item>",
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${esc(opts.title)}</title>
    <link>${esc(base)}</link>
    <description>${esc(opts.description ?? opts.title)}</description>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}
