import { escapeHtml, renderIndex, renderPage } from '../src/templates';
import { Page } from '../src/types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    title: 'Sample Page',
    date: '2026-01-01',
    tags: ['a', 'b'],
    slug: 'sample-page',
    sourcePath: '/content/sample-page.md',
    outputPath: 'sample-page.html',
    html: '<p>Body</p>',
    ...overrides,
  };
}

describe('escapeHtml', () => {
  it('escapes html special characters', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });
});

describe('renderPage', () => {
  it('includes the title, date, tags, and content', () => {
    const html = renderPage(makePage());

    expect(html).toContain('<title>Sample Page</title>');
    expect(html).toContain('<h1>Sample Page</h1>');
    expect(html).toContain('2026-01-01');
    expect(html).toContain('<li>a</li>');
    expect(html).toContain('<li>b</li>');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('href="index.html"');
  });

  it('escapes untrusted title content', () => {
    const html = renderPage(makePage({ title: '<img src=x onerror=alert(1)>' }));
    expect(html).not.toContain('<img src=x onerror=alert(1)>');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('omits the tag list when there are no tags', () => {
    const html = renderPage(makePage({ tags: [] }));
    expect(html).not.toContain('class="tags"');
  });
});

describe('renderIndex', () => {
  it('lists every page sorted by date descending', () => {
    const pages = [
      makePage({ title: 'Older', date: '2026-01-01', outputPath: 'older.html' }),
      makePage({ title: 'Newer', date: '2026-03-01', outputPath: 'newer.html' }),
    ];

    const html = renderIndex(pages);
    const newerIndex = html.indexOf('Newer');
    const olderIndex = html.indexOf('Older');

    expect(newerIndex).toBeGreaterThan(-1);
    expect(olderIndex).toBeGreaterThan(-1);
    expect(newerIndex).toBeLessThan(olderIndex);
    expect(html).toContain('href="newer.html"');
    expect(html).toContain('href="older.html"');
  });

  it('renders an empty list when there are no pages', () => {
    const html = renderIndex([]);
    expect(html).toContain('<ul class="pages">');
  });
});
