import type { Page, SiteConfig } from './types.js';

function escapeXml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function absoluteUrl(baseUrl: string, urlPath: string): string {
  return `${baseUrl.replace(/\/+$/, '')}${urlPath}`;
}

/** Generate an RSS 2.0 feed for the newest `limit` dated pages. */
export function generateRss(pages: Page[], config: SiteConfig, limit = 20): string {
  const items = pages
    .filter((p) => p.frontmatter.date !== null)
    .slice(0, limit)
    .map((p) => {
      const link = absoluteUrl(config.baseUrl, p.url);
      const cats = p.frontmatter.tags
        .map((t) => `      <category>${escapeXml(t)}</category>`)
        .join('\n');
      return [
        '    <item>',
        `      <title>${escapeXml(p.frontmatter.title)}</title>`,
        `      <link>${escapeXml(link)}</link>`,
        `      <guid isPermaLink="true">${escapeXml(link)}</guid>`,
        `      <pubDate>${p.frontmatter.date!.toUTCString()}</pubDate>`,
        `      <description>${escapeXml(p.excerpt)}</description>`,
        ...(cats ? [cats] : []),
        '    </item>',
      ].join('\n');
    })
    .join('\n');

  const lastBuildDate = new Date().toUTCString();
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(config.title)}</title>
    <link>${escapeXml(config.baseUrl)}</link>
    <description>${escapeXml(config.description)}</description>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <atom:link href="${escapeXml(absoluteUrl(config.baseUrl, '/feed.xml'))}" rel="self" type="application/rss+xml"/>
${items}
  </channel>
</rss>
`;
}
