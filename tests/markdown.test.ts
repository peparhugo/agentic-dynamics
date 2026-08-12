import { markdownToHtml } from '../src/markdown';

describe('markdownToHtml', () => {
  it('converts a heading', async () => {
    const html = await markdownToHtml('# Hello');
    expect(html).toContain('<h1>Hello</h1>');
  });

  it('converts emphasis and links', async () => {
    const html = await markdownToHtml('A **bold** [link](https://example.com)');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<a href="https://example.com">link</a>');
  });

  it('converts unordered lists', async () => {
    const html = await markdownToHtml('- one\n- two\n- three');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>one</li>');
    expect(html).toContain('<li>three</li>');
  });

  it('converts fenced code blocks', async () => {
    const html = await markdownToHtml('```ts\nconst x = 1;\n```');
    expect(html).toContain('<pre>');
    expect(html).toContain('<code');
    expect(html).toContain('const x = 1;');
  });

  it('handles an empty string', async () => {
    const html = await markdownToHtml('');
    expect(html).toBe('');
  });
});
