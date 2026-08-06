import { Page } from './types';
import { pathToUrlPath } from './utils';

function escapeXml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export function generateRSS({
  siteTitle,
  siteUrl,
  baseUrl = '',
  pages,
}: {
  siteTitle: string;
  siteUrl: string;
  baseUrl?: string;
  pages: Page[];
}) {
  const items = pages
    .filter((p) => !p.data.draft)
    .sort((a, b) => (new Date(b.data.date || 0).getTime() - new Date(a.data.date || 0).getTime()))
    .map((p) => {
      const urlPath = pathToUrlPath(p.urlPath);
      const link = `${siteUrl}${baseUrl}${baseUrl.endsWith('/') || baseUrl === '' ? '' : '/'}${urlPath}`;
      const title = escapeXml(p.data.title || p.slug);
      const pubDate = p.data.date ? new Date(p.data.date).toUTCString() : new Date().toUTCString();
      const description = escapeXml(p.contentHtml.replace(/<[^>]+>/g, '').slice(0, 280));
      return `\n    <item>\n      <title>${title}</title>\n      <link>${link}</link>\n      <guid>${link}</guid>\n      <pubDate>${pubDate}</pubDate>\n      <description>${description}</description>\n    </item>`;
    })
    .join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${escapeXml(siteTitle)}</title>
    <link>${siteUrl}${baseUrl || ''}</link>
    <description>${escapeXml(siteTitle)}</description>${items}
  </channel>
</rss>
`;
  return xml;
}
