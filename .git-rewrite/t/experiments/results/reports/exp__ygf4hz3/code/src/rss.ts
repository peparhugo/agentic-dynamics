import RSS from 'rss';
import { Page } from './types';

export interface RSSConfig {
  title: string;
  description: string;
  site_url: string;
  feed_url?: string;
  language?: string;
}

export function generateRSS(pages: Page[], config: RSSConfig): string {
  const feed = new RSS({
    title: config.title,
    description: config.description,
    site_url: config.site_url,
    feed_url: config.feed_url || config.site_url + '/feed.xml',
    language: config.language || 'en',
  });

  for (const page of pages) {
    if (page.frontmatter.draft) continue;

    feed.item({
      title: page.frontmatter.title,
      description: page.html,
      url: config.site_url + page.url,
      date: page.frontmatter.date || new Date().toISOString(),
      categories: page.frontmatter.tags,
    });
  }

  return feed.xml({ indent: true });
}
