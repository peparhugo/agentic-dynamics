import { generatePageHtml, generateIndexHtml } from '../src/generator';
import { Page, Frontmatter } from '../src/types';

function makePage(
  overrides: Partial<Frontmatter> & { slug?: string; html?: string },
): Page {
  return {
    frontmatter: {
      title: 'Default Title',
      ...overrides,
    },
    content: '',
    html: overrides.html || '<p>Hello</p>',
    slug: overrides.slug || 'default',
    sourcePath: '/tmp/default.md',
  };
}

describe('generatePageHtml', () => {
  it('generates valid HTML with title', () => {
    const html = generatePageHtml(makePage({ title: 'Test Page' }));
    expect(html).toContain('<title>Test Page</title>');
    expect(html).toContain('<h1>Test Page</h1>');
    expect(html).toContain('<p>Hello</p>');
    expect(html).toContain('<!DOCTYPE html>');
  });

  it('includes date when provided', () => {
    const html = generatePageHtml(makePage({ title: 'Dated', date: '2024-05-10' }));
    expect(html).toContain('<time datetime="2024-05-10">2024-05-10</time>');
  });

  it('includes tags when provided', () => {
    const html = generatePageHtml(makePage({ title: 'Tagged', tags: ['js', 'ts'] }));
    expect(html).toContain('<p>Tags: js, ts</p>');
  });

  it('escapes HTML in title', () => {
    const html = generatePageHtml(makePage({ title: '<script>alert("xss")</script>' }));
    expect(html).toContain('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
    expect(html).not.toContain('<script>');
  });

  it('includes link back to index', () => {
    const html = generatePageHtml(makePage({ title: 'A' }));
    expect(html).toContain('<a href="index.html">Home</a>');
  });
});

describe('generateIndexHtml', () => {
  it('generates index with all pages', () => {
    const pages = [
      makePage({ title: 'Page 1', slug: 'page1' }),
      makePage({ title: 'Page 2', slug: 'page2' }),
    ];
    const html = generateIndexHtml(pages);
    expect(html).toContain('<a href="page1.html">Page 1</a>');
    expect(html).toContain('<a href="page2.html">Page 2</a>');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<h1>All Pages</h1>');
  });

  it('handles empty page list', () => {
    const html = generateIndexHtml([]);
    expect(html).toContain('<ul>\n\n    </ul>');
  });

  it('includes dates and tags in listing', () => {
    const pages = [
      makePage({
        title: 'A Post',
        slug: 'a-post',
        date: '2024-06-01',
        tags: ['news'],
      }),
    ];
    const html = generateIndexHtml(pages);
    expect(html).toContain('2024-06-01');
    expect(html).toContain('news');
  });

  it('escapes HTML in listing', () => {
    const pages = [makePage({ title: '<b>Bold</b>', slug: 'bold' })];
    const html = generateIndexHtml(pages);
    expect(html).toContain('&lt;b&gt;Bold&lt;/b&gt;');
    expect(html).not.toContain('<b>Bold</b>');
  });
});
