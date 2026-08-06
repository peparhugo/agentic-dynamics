import { Post, SiteConfig } from './types';

export function generateRSS(posts: Post[], config: SiteConfig): string {
  const url = config.siteUrl.replace(/\/+$/, '');
  const items = posts.slice(0, 20).map((p) => {
    const pubDate = p.frontmatter.date
      ? new Date(p.frontmatter.date).toUTCString()
      : new Date().toUTCString();
    return [
      '    <item>',
      `      <title>${escapeXml(p.frontmatter.title)}</title>`,
      `      <link>${url}/${p.slug}/</link>`,
      `      <description>${escapeXml(p.html.slice(0, 500))}</description>`,
      `      <pubDate>${pubDate}</pubDate>`,
      `      <guid>${url}/${p.slug}/</guid>`,
      ...(p.frontmatter.tags || []).map(
        (t) => `      <category>${escapeXml(t)}</category>`,
      ),
      '    </item>',
    ].join('\n');
  });

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    '  <channel>',
    `    <title>${escapeXml(config.siteTitle)}</title>`,
    `    <link>${url}</link>`,
    `    <description>${escapeXml(config.siteTitle)} - RSS Feed</description>`,
    `    <atom:link href="${url}/rss.xml" rel="self" type="application/rss+xml"/>`,
    `    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>`,
    items.join('\n'),
    '  </channel>',
    '</rss>',
  ].join('\n');
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
