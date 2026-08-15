import { markdownToHtml } from '../markdown';

describe('markdownToHtml', () => {
  it('renders headings', () => {
    expect(markdownToHtml('# Hello')).toContain('<h1');
    expect(markdownToHtml('## Sub')).toContain('<h2');
  });

  it('renders paragraphs and emphasis', () => {
    const html = markdownToHtml('This is **bold** and *italic*.');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<em>italic</em>');
  });

  it('renders links', () => {
    const html = markdownToHtml('[site](https://example.com)');
    expect(html).toContain('<a href="https://example.com">site</a>');
  });

  it('renders lists', () => {
    const html = markdownToHtml('- one\n- two');
    expect(html).toContain('<li>one</li>');
    expect(html).toContain('<li>two</li>');
  });

  it('renders fenced code blocks', () => {
    const html = markdownToHtml('```js\nconst x = 1;\n```');
    expect(html).toContain('<code');
    expect(html).toContain('const x = 1;');
  });

  it('returns a string (synchronous output)', () => {
    expect(typeof markdownToHtml('# Hi')).toBe('string');
  });
});
