import { renderIndexHtml, renderPageHtml, escapeHtml } from '../src/render';
import { Page } from '../src/types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'post',
    title: 'My Post',
    date: '2024-02-02',
    tags: ['tech'],
    content: 'Body',
    html: '<p>Body</p>',
    sourcePath: 'post.md',
    ...overrides,
  };
}

describe('renderPageHtml', () => {
  it('includes the page title and rendered content', () => {
    const html = renderPageHtml(makePage());
    expect(html).toContain('<h1>My Post</h1>');
    expect(html).toContain('<p>Body</p>');
  });

  it('escapes titles', () => {
    const html = renderPageHtml(makePage({ title: 'A <b>Title</b> & more' }));
    expect(html).not.toContain('<b>Title</b>');
    expect(html).toContain('A &lt;b&gt;Title&lt;/b&gt; &amp; more');
  });

  it('renders tags', () => {
    const html = renderPageHtml(makePage({ tags: ['tech', 'web'] }));
    expect(html).toContain('>tech<');
    expect(html).toContain('>web<');
  });
});

describe('renderIndexHtml', () => {
  it('lists all pages with links to their files', () => {
    const html = renderIndexHtml([
      makePage({ slug: 'one', title: 'One' }),
      makePage({ slug: 'two', title: 'Two' }),
    ]);
    expect(html).toContain('href="one.html"');
    expect(html).toContain('href="two.html"');
    expect(html).toContain('>One</a>');
    expect(html).toContain('>Two</a>');
  });

  it('sorts pages by date, newest first', () => {
    const html = renderIndexHtml([
      makePage({ slug: 'old', title: 'Old', date: '2020-01-01' }),
      makePage({ slug: 'new', title: 'New', date: '2024-01-01' }),
    ]);
    expect(html.indexOf('href="new.html"')).toBeLessThan(html.indexOf('href="old.html"'));
  });
});

describe('escapeHtml', () => {
  it('escapes HTML special characters', () => {
    expect(escapeHtml(`<a href="x">'&'</a>`)).toBe(
      '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;'
    );
  });
});
