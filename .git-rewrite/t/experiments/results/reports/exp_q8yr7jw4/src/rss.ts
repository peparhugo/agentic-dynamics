import type { Post, SiteConfig } from "./types.js";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Generate an RSS 2.0 feed for the given (already sorted, newest first) posts. */
export function generateRss(posts: Post[], site: SiteConfig, limit = 20): string {
  const base = site.baseUrl.replace(/\/$/, "");
  const items = posts.slice(0, limit).map((post) => {
    const url = `${base}${post.url}`;
    const pubDate = post.frontmatter.date ? `\n      <pubDate>${post.frontmatter.date.toUTCString()}</pubDate>` : "";
    const categories = post.frontmatter.tags.map((t) => `\n      <category>${esc(t)}</category>`).join("");
    return `    <item>
      <title>${esc(post.frontmatter.title)}</title>
      <link>${esc(url)}</link>
      <guid>${esc(url)}</guid>
      <description>${esc(post.excerpt)}</description>${pubDate}${categories}
    </item>`;
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${esc(site.title)}</title>
    <link>${esc(base || "/")}</link>
    <description>${esc(site.title)}</description>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items.join("\n")}
  </channel>
</rss>
`;
}
