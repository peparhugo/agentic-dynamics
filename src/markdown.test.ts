import { markdownToHtml } from './markdown';

describe('markdownToHtml', () => {
  it('should convert markdown to HTML', async () => {
    const markdown = '# Hello World';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<h1>Hello World</h1>');
  });

  it('should handle paragraphs', async () => {
    const markdown = 'This is a paragraph.\n\nThis is another paragraph.';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<p>This is a paragraph.</p>');
    expect(html).toContain('<p>This is another paragraph.</p>');
  });

  it('should handle bold and italic', async () => {
    const markdown = '**bold** and *italic*';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<em>italic</em>');
  });

  it('should handle lists', async () => {
    const markdown = '- Item 1\n- Item 2\n- Item 3';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<ul>');
    expect(html).toContain('<li>Item 1</li>');
    expect(html).toContain('<li>Item 2</li>');
    expect(html).toContain('<li>Item 3</li>');
    expect(html).toContain('</ul>');
  });

  it('should handle code blocks', async () => {
    const markdown = '```javascript\nconst x = 1;\n```';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<pre>');
    expect(html).toContain('<code');
  });

  it('should handle inline code', async () => {
    const markdown = 'This is `inline code` in text.';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<code>inline code</code>');
  });

  it('should handle links', async () => {
    const markdown = '[Example](https://example.com)';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<a href="https://example.com">Example</a>');
  });

  it('should handle headings', async () => {
    const markdown = '# H1\n## H2\n### H3';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<h1>H1</h1>');
    expect(html).toContain('<h2>H2</h2>');
    expect(html).toContain('<h3>H3</h3>');
  });

  it('should handle empty content', async () => {
    const markdown = '';
    const html = await markdownToHtml(markdown);

    expect(typeof html).toBe('string');
  });

  it('should handle blockquotes', async () => {
    const markdown = '> This is a quote';
    const html = await markdownToHtml(markdown);

    expect(html).toContain('<blockquote>');
  });
});
