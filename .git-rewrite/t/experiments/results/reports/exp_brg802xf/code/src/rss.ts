import { Page } from './types';

export function generateRss(pages: Page[], siteUrl?: string): string {
  const items = pages
    .filter(p => !p.fm.draft)
    .sort((a, b) => (new Date(b.fm.date || 0).getTime()) - (new Date(a.fm.date || 0).getTime()))
    .map(p => itemXml(p, siteUrl))
    .join('\n');

  const now = new Date().toUTCString();
  const title = 'RSS Feed';
  const link = siteUrl || '';
  const description = 'Site feed';

  return `<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>${escapeXml(title)}</title>
    <link>${escapeXml(link)}</link>
    <description>${escapeXml(description)}</description>
    <lastBuildDate>${now}</lastBuildDate>
${items}
  </channel>
</rss>`;
}

function itemXml(page: Page, siteUrl?: string): string {
  const url = (siteUrl ? siteUrl.replace(/\/$/, '') : '') + page.urlPath;
  const title = page.fm.title || page.urlPath;
  const pubDate = page.fm.date ? new Date(page.fm.date).toUTCString() : '';
  const description = stripTags(page.contentHtml).slice(0, 500);
  return `    <item>
      <title>${escapeXml(title)}</title>
      <link>${escapeXml(url)}</link>
      <guid>${escapeXml(url)}</guid>
      <pubDate>${escapeXml(pubDate)}</pubDate>
      <description>${escapeXml(description)}</description>
    </item>`;
}

function stripTags(html: string): string {
  return html.replace(/<[^>]+>/g, '');
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
