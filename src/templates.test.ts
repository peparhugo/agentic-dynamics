import { escapeHtml, renderIndexHtml, renderPageHtml } from './templates';
import { Page } from './types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'hello',
    frontmatter: { title: 'Hello', date: '2026-01-01', tags: ['a', 'b'] },
    contentHtml: '<p>Body</p>',
    sourcePath: '/content/hello.md',
    ...overrides,
  };
}

describe('escapeHtml', () => {
  it('escapes special characters', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });
});

describe('renderPageHtml', () => {
  it('includes the title, meta, and content', () => {
    const html = renderPageHtml(makePage());
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('2026-01-01');
    expect(html).toContain('a');
    expect(html).toContain('b');
  });

  it('escapes an untrusted title', () => {
    const page = makePage({ frontmatter: { title: '<img src=x>', date: undefined, tags: [] } });
    const html = renderPageHtml(page);
    expect(html).not.toContain('<img src=x>');
    expect(html).toContain('&lt;img src=x&gt;');
  });

  it('links back to a nested index correctly', () => {
    const page = makePage({ slug: 'posts/hello' });
    const html = renderPageHtml(page);
    expect(html).toContain('href="../index.html"');
  });
});

describe('renderIndexHtml', () => {
  it('lists every page with a link to its file', () => {
    const pages = [makePage({ slug: 'a', frontmatter: { title: 'A', tags: [] } }), makePage({ slug: 'b', frontmatter: { title: 'B', tags: [] } })];
    const html = renderIndexHtml(pages, 'My Site');
    expect(html).toContain('<title>My Site</title>');
    expect(html).toContain('href="a.html"');
    expect(html).toContain('href="b.html"');
    expect(html).toContain('>A<');
    expect(html).toContain('>B<');
  });
});
