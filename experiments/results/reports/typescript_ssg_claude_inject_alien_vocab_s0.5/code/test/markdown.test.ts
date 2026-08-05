import { describe, expect, it } from 'vitest';
import { renderMarkdown, extractExcerpt } from '../src/markdown.js';

describe('renderMarkdown', () => {
  it('renders basic markdown', () => {
    const html = renderMarkdown('# Title\n\nSome **bold** text.');
    expect(html).toContain('<h1');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('syntax-highlights fenced code blocks', () => {
    const html = renderMarkdown('```js\nconst x = 42;\n```');
    expect(html).toContain('language-js');
    expect(html).toContain('hljs');
    expect(html).toContain('<span'); // highlight.js token spans
    expect(html).toContain('const');
  });

  it('falls back to plaintext for unknown languages', () => {
    const html = renderMarkdown('```notalang\nhello\n```');
    expect(html).toContain('language-notalang');
    expect(html).toContain('hello');
  });
});

describe('extractExcerpt', () => {
  it('takes the first paragraph, skipping headings and code', () => {
    const md = '# Head\n\n```js\ncode();\n```\n\nFirst real paragraph with [a link](x).';
    expect(extractExcerpt(md)).toBe('First real paragraph with a link.');
  });

  it('truncates long text with an ellipsis', () => {
    const md = 'word '.repeat(100);
    const excerpt = extractExcerpt(md, 50);
    expect(excerpt.length).toBeLessThanOrEqual(50);
    expect(excerpt.endsWith('\u2026')).toBe(true);
  });

  it('returns empty string for empty input', () => {
    expect(extractExcerpt('')).toBe('');
  });
});
