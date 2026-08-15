import { renderMarkdownToHtml } from '../src/markdown';

describe('renderMarkdownToHtml', () => {
  it('renders markdown to HTML', () => {
    const { html } = renderMarkdownToHtml('# Hello\n\nThis is **bold** text.');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('renders lists and links', () => {
    const { html } = renderMarkdownToHtml('- one\n- two\n\n[site](https://example.com)');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>one</li>');
    expect(html).toContain('<a href="https://example.com">site</a>');
  });

  it('extracts frontmatter data without rendering it', () => {
    const markdown = ['---', 'title: Data Title', 'tags: [t1]', '---', '', '## Section'].join('\n');
    const { html, data } = renderMarkdownToHtml(markdown);
    expect(data.title).toBe('Data Title');
    expect(data.tags).toEqual(['t1']);
    expect(html).toContain('<h2>Section</h2>');
    expect(html).not.toContain('Data Title');
  });

  it('handles empty content', () => {
    const { html } = renderMarkdownToHtml('');
    expect(html).toBe('');
  });
});
