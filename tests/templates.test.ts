import { renderIndex, renderPage } from '../src/templates';
import { Page } from '../src/types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    sourcePath: 'hello.md',
    slug: 'hello',
    outputFile: 'hello.html',
    title: 'Hello',
    date: '2024-01-01',
    tags: ['a', 'b'],
    html: '<p>Body</p>',
    ...overrides,
  };
}

describe('renderPage', () => {
  it('includes the title, date, tags and body html', () => {
    const html = renderPage(makePage());

    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('2024-01-01');
    expect(html).toContain('<li>a</li>');
    expect(html).toContain('<li>b</li>');
    expect(html).toContain('<p>Body</p>');
  });

  it('escapes HTML-sensitive characters in the title', () => {
    const html = renderPage(makePage({ title: '<script>alert(1)</script>' }));

    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('omits the tags list when there are no tags', () => {
    const html = renderPage(makePage({ tags: [] }));

    expect(html).not.toContain('class="tags"');
  });
});

describe('renderIndex', () => {
  it('lists all pages sorted by date descending', () => {
    const older = makePage({ slug: 'older', outputFile: 'older.html', title: 'Older', date: '2023-01-01' });
    const newer = makePage({ slug: 'newer', outputFile: 'newer.html', title: 'Newer', date: '2024-06-01' });

    const html = renderIndex([older, newer]);

    const newerIndex = html.indexOf('Newer');
    const olderIndex = html.indexOf('Older');
    expect(newerIndex).toBeGreaterThan(-1);
    expect(olderIndex).toBeGreaterThan(-1);
    expect(newerIndex).toBeLessThan(olderIndex);
  });

  it('links to each page output file', () => {
    const page = makePage();
    const html = renderIndex([page]);

    expect(html).toContain('href="hello.html"');
  });
});
