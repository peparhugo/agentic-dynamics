import { renderMarkdown, renderPageHtml, renderIndexHtml } from '../src/render';
import type { Page } from '../src/types';

describe('renderMarkdown', () => {
  it('converts Markdown to HTML', () => {
    const html = renderMarkdown('# Title\n\nSome **bold** text.');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>bold</strong>');
  });
});

describe('renderPageHtml', () => {
  const page: Page = {
    slug: 'my-post',
    title: 'My <Post>',
    date: '2024-01-01',
    tags: ['a', 'b'],
    html: '<p>Body</p>',
    sourcePath: 'my-post.md',
    outputFile: 'my-post.html',
  };

  it('escapes the title and includes metadata and body html', () => {
    const html = renderPageHtml(page);
    expect(html).toContain('My &lt;Post&gt;');
    expect(html).toContain('2024-01-01');
    expect(html).toContain('<span class="tag">a</span>');
    expect(html).toContain('<span class="tag">b</span>');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('href="index.html"');
  });
});

describe('renderIndexHtml', () => {
  it('lists every page with a link to its output file', () => {
    const pages: Page[] = [
      {
        slug: 'a',
        title: 'Page A',
        date: '2024-01-02',
        tags: [],
        html: '',
        sourcePath: 'a.md',
        outputFile: 'a.html',
      },
      {
        slug: 'b',
        title: 'Page B',
        tags: ['x'],
        html: '',
        sourcePath: 'b.md',
        outputFile: 'b.html',
      },
    ];

    const html = renderIndexHtml(pages);
    expect(html).toContain('href="a.html"');
    expect(html).toContain('Page A');
    expect(html).toContain('href="b.html"');
    expect(html).toContain('Page B');
    expect(html).toContain('<span class="tag">x</span>');
  });
});
