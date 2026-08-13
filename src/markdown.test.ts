import { parseMarkdown } from './markdown';

describe('parseMarkdown', () => {
  it('extracts title, date, and tags from frontmatter', () => {
    const raw = `---
title: My Post
date: 2026-02-01
tags: [foo, bar]
---

# Heading

Some **bold** text.
`;
    const { frontmatter, contentHtml } = parseMarkdown(raw, 'Fallback');

    expect(frontmatter.title).toBe('My Post');
    expect(frontmatter.date).toBe('2026-02-01');
    expect(frontmatter.tags).toEqual(['foo', 'bar']);
    expect(contentHtml).toContain('<h1>Heading</h1>');
    expect(contentHtml).toContain('<strong>bold</strong>');
  });

  it('falls back to the provided title when frontmatter has none', () => {
    const raw = `No frontmatter here.`;
    const { frontmatter } = parseMarkdown(raw, 'Fallback Title');
    expect(frontmatter.title).toBe('Fallback Title');
  });

  it('normalizes a comma separated tags string', () => {
    const raw = `---
title: Tagged
tags: one, two, three
---
Body`;
    const { frontmatter } = parseMarkdown(raw, 'Fallback');
    expect(frontmatter.tags).toEqual(['one', 'two', 'three']);
  });

  it('defaults tags to an empty array when absent', () => {
    const raw = `---
title: No Tags
---
Body`;
    const { frontmatter } = parseMarkdown(raw, 'Fallback');
    expect(frontmatter.tags).toEqual([]);
  });

  it('normalizes a YAML date value (parsed as a Date object) to YYYY-MM-DD', () => {
    const raw = `---
title: Dated
date: 2026-03-15
---
Body`;
    const { frontmatter } = parseMarkdown(raw, 'Fallback');
    expect(frontmatter.date).toBe('2026-03-15');
  });

  it('leaves date undefined when absent', () => {
    const raw = `---
title: No Date
---
Body`;
    const { frontmatter } = parseMarkdown(raw, 'Fallback');
    expect(frontmatter.date).toBeUndefined();
  });
});
