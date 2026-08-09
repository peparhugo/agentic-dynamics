import type { Page, SiteConfig } from './types.js';

export function escapeXml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function absoluteUrl(baseUrl: string, url: string): string {
  return `${baseUrl.replace(/\/+$/, '')}${url}`;
}

/**
 * Generate an RSS 2.0 feed from the given pages.
 * Only pages with a date are included, newest first, capped at `limit`.
 */
export function generateRss(pages: Page[], config: SiteConfig, limit = 20): string {
  const items = pages
    .filter((p) => p.frontmatter.date !== null)
    .sort((a, b) => b.frontmatter.date!.getTime() - a.frontmatter.date!.getTime())
    .slice(0, limit);

  const lastBuildDate = (items[0]?.frontmatter.date ?? new Date()).toUTCString();

  const itemXml = items
    .map((p) => {
      const link = absoluteUrl(config.baseUrl, p.url);
      const description = p.frontmatter.description || p.excerpt;
      const categories = p.frontmatter.tags
        .map((t) => `      <category>${escapeXml(t)}</category>`)
        .join('\n');
      return [
        '    <item>',
        `      <title>${escapeXml(p.frontmatter.title)}</title>`,
        `      <link>${escapeXml(link)}</link>`,
        `      <guid isPermaLink="true">${escapeXml(link)}</guid>`,
        `      <pubDate>${p.frontmatter.date!.toUTCString()}</pubDate>`,
        description ? `      <description>${escapeXml(description)}</description>` : null,
        categories || null,
        '    </item>',
      ]
        .filter((line): line is string => line !== null)
        .join('\n');
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.title)}</title>
    <link>${escapeXml(config.baseUrl)}</link>
    <description>${escapeXml(config.description)}</description>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <atom:link href="${escapeXml(absoluteUrl(config.baseUrl, '/feed.xml'))}" rel="self" type="application/rss+xml"/>
${itemXml}
  </channel>
</rss>
`;
}
