import RSS from 'rss';
import type { Post, SiteConfig } from './types.js';

export function generateRSS(posts: Post[], config: SiteConfig): string {
  const published = posts.filter((p) => !p.frontmatter.draft);

  const feed = new RSS({
    title: config.siteTitle,
    description: config.siteDescription,
    feed_url: `${config.baseUrl}/rss.xml`,
    site_url: config.baseUrl,
    language: 'en',
    pubDate: published.length > 0 ? published[0].frontmatter.date : new Date().toISOString(),
  });

  for (const post of published) {
    feed.item({
      title: post.frontmatter.title,
      description: post.html.slice(0, 500),
      url: `${config.baseUrl}/${post.slug}.html`,
      date: post.frontmatter.date,
      categories: post.frontmatter.tags,
    });
  }

  return feed.xml({ indent: true });
}
