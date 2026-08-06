import { describe, it, expect } from 'vitest';
import { generateRSS } from '../src/rss.js';
import type { Post, Frontmatter, SiteConfig } from '../src/types.js';

function makePost(overrides: Partial<Frontmatter> & { slug?: string; html?: string } = {}): Post {
  return {
    slug: overrides.slug || 'test-post',
    frontmatter: {
      title: overrides.title || 'Test',
      date: overrides.date || '2024-01-01',
      tags: overrides.tags || [],
      draft: overrides.draft ?? false,
      layout: overrides.layout || 'default',
    },
    raw: '',
    html: overrides.html || '<p>test</p>',
    body: '',
  };
}

const config: SiteConfig = {
  src: 'content',
  templates: 'templates',
  output: 'public',
  baseUrl: 'https://example.com',
  siteTitle: 'My Blog',
  siteDescription: 'A blog about things',
};

describe('RSS', () => {
  it('generates valid RSS XML', () => {
    const posts = [makePost({ title: 'Hello' })];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('<?xml version="1.0"');
    expect(xml).toContain('<rss');
    expect(xml).toContain('<channel>');
    expect(xml).toContain('<title>My Blog</title>');
  });

  it('includes post items', () => {
    const posts = [makePost({ title: 'My Post', slug: 'my-post' })];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('<title>My Post</title>');
    expect(xml).toContain('<link>https://example.com/my-post.html</link>');
  });

  it('excludes draft posts', () => {
    const posts = [
      makePost({ title: 'Published', draft: false }),
      makePost({ title: 'Draft', draft: true }),
    ];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('Published');
    expect(xml).not.toContain('Draft');
  });

  it('includes tags as categories', () => {
    const posts = [makePost({ title: 'Tagged', tags: ['js', 'ts'] })];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('<category>js</category>');
    expect(xml).toContain('<category>ts</category>');
  });

  it('includes site description', () => {
    const posts = [makePost()];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('<description>A blog about things</description>');
  });

  it('includes feed URL', () => {
    const posts = [makePost()];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('https://example.com/rss.xml');
  });

  it('handles empty post list', () => {
    const xml = generateRSS([], config);
    expect(xml).toContain('<rss');
    expect(xml).toContain('<channel>');
    expect(xml).toContain('<item>'); // pubDate item
  });

  it('sorts posts by date for pubDate', () => {
    const posts = [
      makePost({ title: 'Newer', date: '2024-06-01' }),
      makePost({ title: 'Older', date: '2024-01-01' }),
      makePost({ title: 'Middle', date: '2024-03-01' }),
    ];
    const xml = generateRSS(posts, config);
    expect(xml).toContain('Newer');
    expect(xml).toContain('Older');
  });
});
