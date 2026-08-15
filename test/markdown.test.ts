import { parseMarkdown, renderMarkdown, normalizeTags } from '../src/markdown';

describe('parseMarkdown', () => {
  it('extracts title, date and tags from YAML frontmatter', () => {
    const source = `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - ssg
---
# Body heading

Some **bold** content.
`;
    const result = parseMarkdown(source);

    expect(result.meta.title).toBe('Hello World');
    expect(result.meta.date).toBe('2024-01-15');
    expect(result.meta.tags).toEqual(['typescript', 'ssg']);
  });

  it('strips frontmatter so the `---` delimiter is never rendered as HTML', () => {
    const source = `---
title: No Delimiters
tags: [a, b]
---
# Heading
`;
    const result = parseMarkdown(source);

    expect(result.content).not.toContain('---');
    expect(result.html).not.toContain('---');
    expect(result.html).toContain('<h1');
  });

  it('returns empty metadata and the full body when there is no frontmatter', () => {
    const source = '# Just a heading\n';
    const result = parseMarkdown(source);

    expect(result.meta.title).toBe('');
    expect(result.meta.tags).toEqual([]);
    expect(result.meta.date).toBeUndefined();
    expect(result.html).toContain('<h1>Just a heading</h1>');
  });

  it('normalizes comma-separated string tags into an array', () => {
    const source = `---
title: Tags
tags: one, two, three
---
Body
`;
    const result = parseMarkdown(source);
    expect(result.meta.tags).toEqual(['one', 'two', 'three']);
  });
});

describe('renderMarkdown', () => {
  it('converts markdown to HTML', () => {
    const html = renderMarkdown('# Title\n\n- item one\n- item two');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<li>item one</li>');
  });
});

describe('normalizeTags', () => {
  it('handles array, string and missing values', () => {
    expect(normalizeTags(['a', 'b'])).toEqual(['a', 'b']);
    expect(normalizeTags('a, b')).toEqual(['a', 'b']);
    expect(normalizeTags(undefined)).toEqual([]);
    expect(normalizeTags(null)).toEqual([]);
  });
});
