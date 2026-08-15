import { renderMarkdown } from '../src/markdown';

describe('renderMarkdown', () => {
  it('converts headings to HTML', () => {
    const html = renderMarkdown('# Hello');
    expect(html).toContain('<h1>Hello</h1>');
  });

  it('converts paragraphs and emphasis to HTML', () => {
    const html = renderMarkdown('This is **bold** and *italic*.');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<em>italic</em>');
  });

  it('converts lists to HTML', () => {
    const html = renderMarkdown('- one\n- two');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>one</li>');
  });
});
