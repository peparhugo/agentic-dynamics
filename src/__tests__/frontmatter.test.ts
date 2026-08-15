import { parseFrontmatter } from '../frontmatter.js';

describe('Frontmatter parser', () => {
  it('should parse YAML frontmatter with title', () => {
    const content = `---
title: Hello World
---
This is content.`;

    const result = parseFrontmatter(content);
    expect(result.data.title).toBe('Hello World');
    expect(result.content).toBe('This is content.');
  });

  it('should parse multiple fields', () => {
    const content = `---
title: My Post
date: 2024-01-15
---
Content here.`;

    const result = parseFrontmatter(content);
    expect(result.data.title).toBe('My Post');
    expect(result.data.date).toBe('2024-01-15');
    expect(result.content).toBe('Content here.');
  });

  it('should parse tags as array', () => {
    const content = `---
title: Post
tags: [javascript, typescript, web]
---
Content.`;

    const result = parseFrontmatter(content);
    expect(result.data.tags).toEqual(['javascript', 'typescript', 'web']);
  });

  it('should handle missing frontmatter', () => {
    const content = `This is just content without frontmatter.`;

    const result = parseFrontmatter(content);
    expect(result.data).toEqual({});
    expect(result.content).toBe('This is just content without frontmatter.');
  });

  it('should handle incomplete frontmatter', () => {
    const content = `---
title: Incomplete

This is content.`;

    const result = parseFrontmatter(content);
    expect(result.data).toEqual({});
    expect(result.content).toBe(`---
title: Incomplete

This is content.`);
  });

  it('should parse boolean values', () => {
    const content = `---
published: true
archived: false
---
Content.`;

    const result = parseFrontmatter(content);
    expect(result.data.published).toBe(true);
    expect(result.data.archived).toBe(false);
  });

  it('should parse numeric values', () => {
    const content = `---
year: 2024
count: 42
rating: 4.5
---
Content.`;

    const result = parseFrontmatter(content);
    expect(result.data.year).toBe(2024);
    expect(result.data.count).toBe(42);
    expect(result.data.rating).toBe(4.5);
  });

  it('should handle whitespace around delimiters', () => {
    const content = `---
title:   Spaced Title
description:   A description
---
Content with spaces.`;

    const result = parseFrontmatter(content);
    expect(result.data.title).toBe('Spaced Title');
    expect(result.data.description).toBe('A description');
    expect(result.content).toBe('Content with spaces.');
  });

  it('should preserve multiline content', () => {
    const content = `---
title: Post
---
Line 1
Line 2
Line 3`;

    const result = parseFrontmatter(content);
    expect(result.data.title).toBe('Post');
    expect(result.content).toBe('Line 1\nLine 2\nLine 3');
  });
});
