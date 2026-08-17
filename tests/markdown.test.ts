import { renderMarkdown } from '../src/markdown';

describe('renderMarkdown', () => {
  it('converts a heading to HTML', () => {
    expect(renderMarkdown('# Hello')).toContain('<h1>Hello</h1>');
  });

  it('converts paragraphs and emphasis', () => {
    const html = renderMarkdown('Some *emphasized* **text**.');
    expect(html).toContain('<em>emphasized</em>');
    expect(html).toContain('<strong>text</strong>');
  });

  it('converts links and lists', () => {
    const html = renderMarkdown('- one\n- two\n\n[link](https://example.com)');
    expect(html).toContain('<li>one</li>');
    expect(html).toContain('<li>two</li>');
    expect(html).toContain('href="https://example.com"');
  });
});
