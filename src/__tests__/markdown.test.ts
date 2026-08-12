import { parseFrontmatter, renderMarkdown } from '../markdown';

describe('parseFrontmatter', () => {
  it('parses title, date, and tags from frontmatter', () => {
    const source = `---
title: Hello World
date: 2024-01-15
tags: [typescript, web]
---
# Heading
Some **bold** text.
`;

    const result = parseFrontmatter(source);
    expect(result.title).toBe('Hello World');
    expect(result.date).toBe('2024-01-15T00:00:00.000Z');
    expect(result.tags).toEqual(['typescript', 'web']);
    expect(result.body).toContain('# Heading');
  });

  it('parses tags given as a comma-separated string', () => {
    const source = `---
title: Comma Tags
tags: one, two, three
---
Body
`;
    const result = parseFrontmatter(source);
    expect(result.tags).toEqual(['one', 'two', 'three']);
  });

  it('handles missing frontmatter gracefully', () => {
    const result = parseFrontmatter('Just a plain markdown body.');
    expect(result.title).toBeUndefined();
    expect(result.date).toBeUndefined();
    expect(result.tags).toEqual([]);
    expect(result.body).toBe('Just a plain markdown body.');
  });
});

describe('renderMarkdown', () => {
  it('is asynchronous and returns HTML', async () => {
    const html = await renderMarkdown('# Title\n\nHello **world**');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>world</strong>');
  });

  it('awaits the async parse() promise (marked v12+)', async () => {
    const promise = renderMarkdown('## Async parse');
    expect(promise).toBeInstanceOf(Promise);
    const html = await promise;
    expect(html).toContain('<h2>Async parse</h2>');
  });
});
