import { describe, it, expect } from 'vitest';
import { renderMarkdown, extractExcerpt } from '../src/markdown.js';

describe('renderMarkdown', () => {
  it('renders basic markdown', () => {
    const html = renderMarkdown('# Title\n\nSome **bold** text.');
    expect(html).toContain('<h1');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('syntax-highlights fenced code blocks with a language', () => {
    const html = renderMarkdown('```ts\nconst x: number = 1;\n```');
    expect(html).toContain('class="hljs language-ts"');
    expect(html).toContain('hljs-'); // token spans present
  });

  it('auto-highlights code blocks without a language', () => {
    const html = renderMarkdown('```\nfunction f() { return 1; }\n```');
    expect(html).toContain('<pre><code');
    expect(html).toContain('hljs-');
  });
});

describe('extractExcerpt', () => {
  it('uses the first paragraph, skipping headings', () => {
    expect(extractExcerpt('# H\n\nFirst para.\n\nSecond.')).toBe('First para.');
  });
  it('strips inline markdown', () => {
    expect(extractExcerpt('Some *emphasis* and a [link](http://x).')).toBe(
      'Some emphasis and a link.',
    );
  });
  it('truncates long text with an ellipsis', () => {
    const out = extractExcerpt('word '.repeat(100), 50);
    expect(out.length).toBeLessThanOrEqual(50);
    expect(out.endsWith('\u2026')).toBe(true);
  });
});
