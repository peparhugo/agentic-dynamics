import { parseMarkdown, slugify } from '../src/markdown';

describe('parseMarkdown', () => {
  it('extracts frontmatter and renders markdown', () => {
    const doc = parseMarkdown(
      'hello-world',
      `---
title: Hello World
date: 2026-01-15
tags: [intro, meta]
---

# Hello World
`,
    );
    expect(doc.title).toBe('Hello World');
    expect(doc.date).toBe('2026-01-15T00:00:00.000Z');
    expect(doc.tags).toEqual(['intro', 'meta']);
    expect(doc.content).toContain('<h1>Hello World</h1>');
  });

  it('falls back to the slug as title when frontmatter has no title', () => {
    const doc = parseMarkdown('my-page', '# Just a heading');
    expect(doc.title).toBe('my-page');
    expect(doc.content).toContain('<h1>Just a heading</h1>');
  });

  it('parses comma separated tags', () => {
    const doc = parseMarkdown('p', '---\ntags: a, b, c\n---\nBody');
    expect(doc.tags).toEqual(['a', 'b', 'c']);
  });

  it('returns empty tags when missing', () => {
    const doc = parseMarkdown('p', '# No frontmatter');
    expect(doc.tags).toEqual([]);
  });

  it('renders markdown emphasis', () => {
    const doc = parseMarkdown('p', '**bold** and *italic*');
    expect(doc.content).toContain('<strong>bold</strong>');
    expect(doc.content).toContain('<em>italic</em>');
  });
});

describe('slugify', () => {
  it('strips the .md extension', () => {
    expect(slugify('post.md')).toBe('post');
    expect(slugify('post.markdown')).toBe('post');
  });
});
