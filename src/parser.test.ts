import { parseMarkdownWithYaml, parseMarkdown, type PageMetadata } from './parser';

describe('parseMarkdownWithYaml', () => {
  it('parses YAML frontmatter with title', async () => {
    const content = `---
title: Hello World
---
# Content
This is a test.`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.title).toBe('Hello World');
    expect(result.content).toContain('<h1>Content</h1>');
  });

  it('parses YAML frontmatter with date', async () => {
    const content = `---
title: My Post
date: 2024-01-15
---
# Post Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.title).toBe('My Post');
    expect(result.metadata.date).toBe('2024-01-15');
  });

  it('parses YAML frontmatter with tags', async () => {
    const content = `---
title: Tagged Post
tags: typescript, testing, ssg
---
# Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.tags).toEqual(['typescript', 'testing', 'ssg']);
  });

  it('parses YAML frontmatter with multiple fields', async () => {
    const content = `---
title: Full Example
date: 2024-01-15
tags: test, example
author: John Doe
---
# Full Example

This is the content.`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.title).toBe('Full Example');
    expect(result.metadata.date).toBe('2024-01-15');
    expect(result.metadata.tags).toEqual(['test', 'example']);
    expect(result.metadata.author).toBe('John Doe');
    expect(result.content).toContain('<h1>Full Example</h1>');
    expect(result.content).toContain('This is the content');
  });

  it('handles markdown without frontmatter', async () => {
    const content = `# No Frontmatter

This is just markdown.`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.title).toBeUndefined();
    expect(result.content).toContain('<h1>No Frontmatter</h1>');
    expect(result.content).toContain('This is just markdown');
  });

  it('handles empty tags field', async () => {
    const content = `---
title: No Tags
tags:
---
Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.tags).toBeUndefined();
  });

  it('preserves markdown formatting', async () => {
    const content = `---
title: Formatted
---
**bold** and *italic* and [link](http://example.com)`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.content).toContain('<strong>bold</strong>');
    expect(result.content).toContain('<em>italic</em>');
    expect(result.content).toContain('href="http://example.com"');
  });

  it('handles code blocks', async () => {
    const content = `---
title: Code
---
\`\`\`typescript
const x = 42;
\`\`\``;

    const result = await parseMarkdownWithYaml(content);

    expect(result.content).toContain('<pre>');
    expect(result.content).toContain('const x = 42');
  });

  it('strips whitespace from tag values', async () => {
    const content = `---
title: Test
tags: tag1 , tag2 , tag3
---
Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.tags).toEqual(['tag1', 'tag2', 'tag3']);
  });
});

describe('parseMarkdown', () => {
  it('parses JSON frontmatter via gray-matter', async () => {
    const content = `---
title: "JSON Test"
tags: ["a", "b"]
---
# Content`;

    const result = await parseMarkdown(content);

    expect(result.metadata.title).toBe('JSON Test');
    expect(Array.isArray(result.metadata.tags)).toBe(true);
  });

  it('handles markdown without any frontmatter', async () => {
    const content = `# No Frontmatter
Just content.`;

    const result = await parseMarkdown(content);

    expect(result.metadata).toEqual({});
    expect(result.content).toContain('<h1>No Frontmatter</h1>');
  });
});

describe('template and layout metadata', () => {
  it('parses template metadata', async () => {
    const content = `---
title: Test
template: custom.hbs
---
Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.template).toBe('custom.hbs');
  });

  it('parses layout metadata', async () => {
    const content = `---
title: Test
layout: page.hbs
---
Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.layout).toBe('page.hbs');
  });

  it('parses both template and layout together', async () => {
    const content = `---
title: Test
template: custom.hbs
layout: page.hbs
---
Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.template).toBe('custom.hbs');
    expect(result.metadata.layout).toBe('page.hbs');
  });

  it('returns undefined for missing template and layout', async () => {
    const content = `---
title: Test
---
Content`;

    const result = await parseMarkdownWithYaml(content);

    expect(result.metadata.template).toBeUndefined();
    expect(result.metadata.layout).toBeUndefined();
  });
});
