import { parseMarkdown } from '../src/markdown';

describe('parseMarkdown', () => {
  it('parses YAML frontmatter with title, date and tags', () => {
    const md = `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - ssg
---
# Heading

Some body text.
`;
    const { frontmatter, html, body } = parseMarkdown(md);

    expect(frontmatter.title).toBe('Hello World');
    expect(frontmatter.date).toBeInstanceOf(Date);
    expect((frontmatter.date as Date).toISOString()).toBe(
      '2024-01-15T00:00:00.000Z'
    );
    expect(frontmatter.tags).toEqual(['typescript', 'ssg']);
    expect(html).toContain('<h1>Heading</h1>');
    expect(html).toContain('Some body text.');
    expect(body).not.toContain('---');
  });

  it('supports comma-separated tags as a string', () => {
    const md = `---
title: Post
tags: a, b, c
---
Text`;
    const { frontmatter } = parseMarkdown(md);
    expect(frontmatter.tags).toBe('a, b, c');
  });

  it('handles documents without frontmatter', () => {
    const md = `# No Frontmatter

Just content.`;
    const { frontmatter, html } = parseMarkdown(md);

    expect(frontmatter).toEqual({});
    expect(html).toContain('<h1>No Frontmatter</h1>');
    expect(html).toContain('Just content.');
  });

  it('does not render the frontmatter delimiter as a horizontal rule', () => {
    const md = `---
title: No Hr
---
# Content`;
    const { html } = parseMarkdown(md);
    expect(html).not.toContain('<hr');
  });

  it('renders inline markdown such as links and emphasis', () => {
    const md = `---
title: Inline
---
Read the [docs](https://example.com) *now*.`;
    const { html } = parseMarkdown(md);
    expect(html).toContain('<a href="https://example.com">docs</a>');
    expect(html).toContain('<em>now</em>');
  });

  it('strips CRLF frontmatter delimiters', () => {
    const md = '---\r\ntitle: Windows\r\n---\r\n# Body';
    const { html, body } = parseMarkdown(md);
    expect(body).not.toContain('---');
    expect(html).toContain('<h1>Body</h1>');
  });
});
