import { Page } from './types';
import { renderIndex, renderPage } from './render';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'about',
    content: '# About',
    html: '<h1>About</h1>',
    data: {},
    ...overrides,
  };
}

describe('renderPage', () => {
  it('uses the frontmatter title in the <title> and <h1>', () => {
    const html = renderPage(makePage({ data: { title: 'About Me' } }));
    expect(html).toContain('<title>About Me</title>');
    expect(html).toContain('<h1>About Me</h1>');
  });

  it('falls back to the slug for the title', () => {
    const html = renderPage(makePage({ slug: 'my-page' }));
    expect(html).toContain('<title>my-page</title>');
    expect(html).toContain('<h1>my-page</h1>');
  });

  it('renders the date and tags when present', () => {
    const html = renderPage(
      makePage({ data: { date: '2024-01-02', tags: ['a', 'b'] } })
    );
    expect(html).toContain('<time datetime="2024-01-02">2024-01-02</time>');
    expect(html).toContain('class="tag">a</span>');
    expect(html).toContain('class="tag">b</span>');
  });

  it('escapes unsafe title characters', () => {
    const html = renderPage(makePage({ data: { title: 'A <B> & "C"' } }));
    expect(html).toContain('&lt;B&gt;');
    expect(html).not.toContain('<B>');
  });
});

describe('renderIndex', () => {
  it('links every page by slug', () => {
    const pages = [
      makePage({ slug: 'a', data: { title: 'A' } }),
      makePage({ slug: 'b', data: { title: 'B' } }),
    ];
    const html = renderIndex(pages);
    expect(html).toContain('<a href="a.html">A</a>');
    expect(html).toContain('<a href="b.html">B</a>');
  });

  it('sorts pages by date descending', () => {
    const pages = [
      makePage({ slug: 'old', data: { date: '2023-01-01' } }),
      makePage({ slug: 'new', data: { date: '2024-01-01' } }),
    ];
    const html = renderIndex(pages);
    expect(html.indexOf('new.html')).toBeLessThan(html.indexOf('old.html'));
  });
});
