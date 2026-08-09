import type { Page, SiteConfig } from './types.js';

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function absoluteUrl(baseUrl: string, url: string): string {
  return baseUrl.replace(/\/$/, '') + url;
}

/**
 * Generate an RSS 2.0 feed. Pages are sorted newest-first by date;
 * undated pages sort last. Draft pages must be filtered before calling.
 */
export function generateRss(pages: Page[], config: SiteConfig, limit = 20): string {
  const sorted = [...pages].sort(
    (a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0),
  );

  const items = sorted
    .slice(0, limit)
    .map((page) => {
      const link = absoluteUrl(config.baseUrl, page.url);
      const pubDate = page.frontmatter.date ? `\n      <pubDate>${page.frontmatter.date.toUTCString()}</pubDate>` : '';
      const categories = page.frontmatter.tags
        .map((t) => `\n      <category>${escapeXml(t)}</category>`)
        .join('');
      return `    <item>
      <title>${escapeXml(page.frontmatter.title)}</title>
      <link>${escapeXml(link)}</link>
      <guid>${escapeXml(link)}</guid>
      <description>${escapeXml(page.excerpt)}</description>${pubDate}${categories}
    </item>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.title)}</title>
    <link>${escapeXml(config.baseUrl)}</link>
    <description>${escapeXml(config.description)}</description>
    <atom:link href="${escapeXml(absoluteUrl(config.baseUrl, '/feed.xml'))}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
}
