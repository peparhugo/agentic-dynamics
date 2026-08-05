import type { Page, SiteConfig } from './types.js';

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/** Generate an RSS 2.0 feed for the given pages (newest first). */
export function generateRss(pages: Page[], config: SiteConfig, now = new Date()): string {
  const base = config.baseUrl.replace(/\/$/, '');
  const items = [...pages]
    .filter((p) => p.frontmatter.date)
    .sort((a, b) => b.frontmatter.date!.getTime() - a.frontmatter.date!.getTime())
    .map((p) => {
      const link = `${base}${p.url}`;
      return [
        '    <item>',
        `      <title>${escapeXml(p.frontmatter.title)}</title>`,
        `      <link>${escapeXml(link)}</link>`,
        `      <guid>${escapeXml(link)}</guid>`,
        `      <pubDate>${p.frontmatter.date!.toUTCString()}</pubDate>`,
        p.frontmatter.tags.length
          ? p.frontmatter.tags.map((t) => `      <category>${escapeXml(t)}</category>`).join('\n')
          : null,
        `      <description>${escapeXml(p.excerpt)}</description>`,
        '    </item>',
      ]
        .filter((l): l is string => l != null)
        .join('\n');
    });

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0">',
    '  <channel>',
    `    <title>${escapeXml(config.title)}</title>`,
    `    <link>${escapeXml(base)}</link>`,
    `    <description>${escapeXml(config.description)}</description>`,
    `    <lastBuildDate>${now.toUTCString()}</lastBuildDate>`,
    ...items,
    '  </channel>',
    '</rss>',
    '',
  ].join('\n');
}
