import { renderMarkdown, renderIndexBodyHtml } from '../src/render';
import type { Page } from '../src/types';

describe('renderMarkdown', () => {
  it('converts Markdown to HTML', () => {
    const html = renderMarkdown('# Title\n\nSome **bold** text.');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>bold</strong>');
  });
});

describe('renderIndexBodyHtml', () => {
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

    const html = renderIndexBodyHtml(pages);
    expect(html).toContain('href="a.html"');
    expect(html).toContain('Page A');
    expect(html).toContain('2024-01-02');
    expect(html).toContain('href="b.html"');
    expect(html).toContain('Page B');
    expect(html).toContain('<span class="tag">x</span>');
  });

  it('escapes title and output file values', () => {
    const pages: Page[] = [
      {
        slug: 'c',
        title: 'A <script> Title',
        tags: [],
        html: '',
        sourcePath: 'c.md',
        outputFile: 'c.html',
      },
    ];

    const html = renderIndexBodyHtml(pages);
    expect(html).toContain('A &lt;script&gt; Title');
    expect(html).not.toContain('<script>');
  });
});
