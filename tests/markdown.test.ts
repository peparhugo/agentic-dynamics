import { parseMarkdown, renderMarkdown } from '../src/markdown';

describe('parseMarkdown', () => {
  it('extracts frontmatter fields', () => {
    const raw = `---
title: Hello World
date: 2024-01-15
tags: [typescript, ssg]
---
# Body
`;
    const { data, body } = parseMarkdown(raw);
    expect(data.title).toBe('Hello World');
    expect(data.date).toBe('2024-01-15');
    expect(data.tags).toEqual(['typescript', 'ssg']);
    expect(body).toContain('# Body');
  });

  it('handles documents without frontmatter', () => {
    const { data, body } = parseMarkdown('Just some text');
    expect(data).toEqual({});
    expect(body).toBe('Just some text');
  });
});

describe('renderMarkdown', () => {
  it('renders markdown to html', () => {
    const html = renderMarkdown('# Title\n\nSome **bold** text.');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>bold</strong>');
  });
});
