import { parseArgs } from '../src/cli';
import { parsePage, renderIndex } from '../src/index';

describe('page parsing', () => {
  it('keeps ISO dates as strings and supports comma-separated tags', () => {
    const page = parsePage(`---
title: Entry
date: 2025-01-02
tags: one, two
---
Body`, '/content/entry.md');

    expect(page.date).toBe('2025-01-02');
    expect(typeof page.date).toBe('string');
    expect(page.tags).toEqual(['one', 'two']);
  });

  it('escapes metadata rendered into generated templates', () => {
    const page = parsePage('---\ntitle: <script>alert(1)</script>\n---\nText', '/content/x.md');
    const index = renderIndex([page]);
    expect(index).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(index).not.toContain('<script>');
  });

  it('only unescapes actual raw HTML, not code or escaped text', () => {
    const page = parsePage('`<b>code</b>`\n\n&lt;i&gt;text&lt;/i&gt;\n\n<strong>raw</strong>', '/content/x.md');
    expect(page.html).toContain('<code>&lt;b&gt;code&lt;/b&gt;</code>');
    expect(page.html).toContain('&lt;i&gt;text&lt;/i&gt;');
    expect(page.html).toContain('<strong>raw</strong>');
  });
});

describe('CLI arguments', () => {
  it('reads build paths', () => {
    expect(parseArgs(['build', '--content', 'posts', '--output', 'public', '--templates', 'theme'])).toEqual({
      command: 'build',
      contentDir: 'posts',
      outputDir: 'public',
      templatesDir: 'theme',
    });
  });

  it('rejects invalid and incomplete options', () => {
    expect(() => parseArgs(['build', '--other'])).toThrow('Unknown option');
    expect(() => parseArgs(['build', '--content'])).toThrow('Missing value');
  });
});
