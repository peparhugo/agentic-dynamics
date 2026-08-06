import { writeFileSync } from 'node:fs';
import { Post, SiteConfig } from './types';

export function generateRSS(posts: Post[], config: SiteConfig): string {
  const items = posts.slice(0, 20).map((p) => {
    const url = `${config.siteUrl}/${p.slug}/`;
    return `<item>
      <title><![CDATA[${p.title}]]></title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <pubDate>${p.date.toUTCString()}</pubDate>
      <description><![CDATA[${p.html.slice(0, 500)}]]></description>
    </item>`;
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${config.siteTitle}</title>
    <link>${config.siteUrl}</link>
    <description>${config.siteTitle} RSS Feed</description>
    <atom:link href="${config.siteUrl}/feed.xml" rel="self" type="application/rss+xml"/>
    ${items.join('\n    ')}
  </channel>
</rss>`;
}

export function writeRSS(posts: Post[], config: SiteConfig): void {
  const xml = generateRSS(posts, config);
  writeFileSync(`${config.outputDir}/feed.xml`, xml, 'utf-8');
}
