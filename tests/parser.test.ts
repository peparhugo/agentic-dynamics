import { parseMarkdown } from '../src/parser';

describe('parseMarkdown', () => {
  it('extracts frontmatter fields', () => {
    const raw = `---
title: Hello World
date: 2024-01-15
tags: [intro, news]
---

# Hi there

Some *content*.
`;
    const page = parseMarkdown(raw, 'hello-world.md');

    expect(page.title).toBe('Hello World');
    expect(page.date).toBe('2024-01-15');
    expect(page.tags).toEqual(['intro', 'news']);
    expect(page.slug).toBe('hello-world');
    expect(page.outputFile).toBe('hello-world.html');
  });

  it('renders markdown body to HTML', () => {
    const raw = `---
title: Test
---
# Heading

A paragraph with **bold** text.
`;
    const page = parseMarkdown(raw, 'test.md');

    expect(page.html).toContain('<h1>Heading</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
  });

  it('falls back to a title derived from the filename when missing', () => {
    const raw = `No frontmatter here.\n`;
    const page = parseMarkdown(raw, 'my-cool-post.md');

    expect(page.title).toBe('My Cool Post');
  });

  it('handles comma-separated string tags', () => {
    const raw = `---
title: Tagged
tags: "one, two, three"
---
Body
`;
    const page = parseMarkdown(raw, 'tagged.md');

    expect(page.tags).toEqual(['one', 'two', 'three']);
  });

  it('defaults tags to an empty array when absent', () => {
    const raw = `---
title: No Tags
---
Body
`;
    const page = parseMarkdown(raw, 'no-tags.md');

    expect(page.tags).toEqual([]);
  });

  it('preserves nested directory structure in the slug', () => {
    const raw = `---
title: Nested
---
Body
`;
    const page = parseMarkdown(raw, 'posts/2024/nested.md');

    expect(page.slug).toBe('posts/2024/nested');
    expect(page.outputFile).toBe('posts/2024/nested.html');
  });

  it('leaves date undefined when absent from frontmatter', () => {
    const raw = `---
title: No Date
---
Body
`;
    const page = parseMarkdown(raw, 'no-date.md');

    expect(page.date).toBeUndefined();
  });
});
