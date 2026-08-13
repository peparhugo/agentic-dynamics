import { markdownToHtml } from './markdown';

describe('Markdown to HTML', () => {
  it('should convert heading to HTML', () => {
    const md = '# Hello World';
    const html = markdownToHtml(md);
    expect(html).toContain('<h1>Hello World</h1>');
  });

  it('should convert paragraph to HTML', () => {
    const md = 'This is a paragraph.';
    const html = markdownToHtml(md);
    expect(html).toContain('<p>This is a paragraph.</p>');
  });

  it('should convert bold text', () => {
    const md = 'This is **bold** text.';
    const html = markdownToHtml(md);
    expect(html).toContain('<strong>bold</strong>');
  });

  it('should convert italic text', () => {
    const md = 'This is *italic* text.';
    const html = markdownToHtml(md);
    expect(html).toContain('<em>italic</em>');
  });

  it('should convert links', () => {
    const md = 'Check out [my site](https://example.com)';
    const html = markdownToHtml(md);
    expect(html).toContain('<a href="https://example.com">my site</a>');
  });

  it('should convert lists', () => {
    const md = `- Item 1
- Item 2
- Item 3`;
    const html = markdownToHtml(md);
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>Item 1</li>');
    expect(html).toContain('</ul>');
  });

  it('should convert code blocks', () => {
    const md = '```\nconst x = 42;\n```';
    const html = markdownToHtml(md);
    expect(html).toContain('<code>');
    expect(html).toContain('const x = 42;');
  });

  it('should convert inline code', () => {
    const md = 'Use `const` to declare variables.';
    const html = markdownToHtml(md);
    expect(html).toContain('<code>const</code>');
  });

  it('should convert blockquotes', () => {
    const md = '> This is a quote';
    const html = markdownToHtml(md);
    expect(html).toContain('<blockquote>');
    expect(html).toContain('This is a quote');
  });

  it('should handle multiple paragraphs', () => {
    const md = `First paragraph.

Second paragraph.

Third paragraph.`;
    const html = markdownToHtml(md);
    const matches = html.match(/<p>/g);
    expect(matches?.length).toBe(3);
  });

  it('should handle complex markdown', () => {
    const md = `# Main Heading

This is a paragraph with **bold** and *italic*.

## Sub-heading

- List item 1
- List item 2

> A quote for emphasis

\`\`\`
code block
\`\`\``;
    const html = markdownToHtml(md);
    expect(html).toContain('<h1>Main Heading</h1>');
    expect(html).toContain('<h2>Sub-heading</h2>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<ul>');
    expect(html).toContain('<blockquote>');
  });
});
