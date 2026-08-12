import { parseMarkdown, renderMarkdown } from '../src/parser';

describe('parseMarkdown', () => {
  it('strips YAML frontmatter delimited by --- and exposes the data', () => {
    const raw = `---
title: Hello World
date: 2024-01-15
tags: [intro, guide]
---
# Heading

Some **bold** text.
`;

    const { data, body } = parseMarkdown(raw);

    expect(data.title).toBe('Hello World');
    expect(data.date).toBe('2024-01-15');
    expect(data.tags).toEqual(['intro', 'guide']);
    expect(body).toContain('# Heading');
    expect(body).toContain('Some **bold** text.');
    expect(body).not.toContain('---');
    expect(body).not.toContain('title: Hello World');
  });

  it('supports string tag lists', () => {
    const raw = `---
title: Tags
tags: one, two, three
---
Body
`;

    const { data } = parseMarkdown(raw);
    expect(data.title).toBe('Tags');
    expect(String(data.tags)).toContain('one');
  });

  it('returns empty data and full body when there is no frontmatter', () => {
    const { data, body } = parseMarkdown('# Just a heading\n\nplain text');

    expect(data).toEqual({});
    expect(body).toContain('# Just a heading');
    expect(body).toContain('plain text');
  });

  it('returns empty data for a doc that is only frontmatter', () => {
    const raw = `---
title: Only Metadata
---
`;

    const { data, body } = parseMarkdown(raw);
    expect(data.title).toBe('Only Metadata');
    expect(body).toBe('');
  });

  it('leaves the frontmatter out of the trimmed body', () => {
    const raw = `---
title: A
---
First line

Second line.
`;

    const { body } = parseMarkdown(raw);
    expect(body.split('\n').length).toBeGreaterThan(1);
    expect(body.startsWith('First line')).toBe(true);
  });
});

describe('renderMarkdown', () => {
  it('renders headings, emphasis and links to HTML', () => {
    const html = renderMarkdown('# Big Title\n\nA paragraph with **bold** and [a link](http://x.test).');

    expect(html).toContain('<h1>Big Title</h1>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<a href="http://x.test">a link</a>');
  });

  it('renders lists', () => {
    const html = renderMarkdown('- one\n- two\n- three');
    expect(html).toContain('<li>one</li>');
    expect(html).toContain('<li>two</li>');
    expect(html).toContain('<li>three</li>');
  });

  it('renders empty source to empty output', () => {
    expect(renderMarkdown('')).toBe('');
  });
});
