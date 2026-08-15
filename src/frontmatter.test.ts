import { parseFrontmatter } from './frontmatter';

describe('parseFrontmatter', () => {
  it('should parse YAML frontmatter', () => {
    const content = `---
title: My Post
date: 2024-01-15
---
# Content here`;

    const result = parseFrontmatter(content);

    expect(result.data.title).toBe('My Post');
    expect(result.data.date).toBe('2024-01-15');
    expect(result.content).toBe('# Content here');
  });

  it('should handle tags as array', () => {
    const content = `---
title: Test
tags: [javascript, typescript, testing]
---
Content`;

    const result = parseFrontmatter(content);

    expect(Array.isArray(result.data.tags)).toBe(true);
    expect(result.data.tags).toEqual(['javascript', 'typescript', 'testing']);
  });

  it('should handle quoted strings', () => {
    const content = `---
title: "My Title with Spaces"
author: 'John Doe'
---
Content`;

    const result = parseFrontmatter(content);

    expect(result.data.title).toBe('My Title with Spaces');
    expect(result.data.author).toBe('John Doe');
  });

  it('should handle boolean values', () => {
    const content = `---
published: true
draft: false
---
Content`;

    const result = parseFrontmatter(content);

    expect(result.data.published).toBe(true);
    expect(result.data.draft).toBe(false);
  });

  it('should handle missing frontmatter', () => {
    const content = '# No frontmatter\nJust content';

    const result = parseFrontmatter(content);

    expect(result.data).toEqual({});
    expect(result.content).toBe('# No frontmatter\nJust content');
  });

  it('should handle unclosed frontmatter', () => {
    const content = `---
title: Unclosed
# No closing delimiter
Content`;

    const result = parseFrontmatter(content);

    expect(result.data).toEqual({});
    expect(result.content).toBe(content);
  });

  it('should handle empty frontmatter', () => {
    const content = `---
---
Content here`;

    const result = parseFrontmatter(content);

    expect(result.data).toEqual({});
    expect(result.content).toBe('Content here');
  });

  it('should skip comment lines in frontmatter', () => {
    const content = `---
title: My Post
# This is a comment
date: 2024-01-15
---
Content`;

    const result = parseFrontmatter(content);

    expect(result.data.title).toBe('My Post');
    expect(result.data.date).toBe('2024-01-15');
  });

  it('should handle whitespace-only lines', () => {
    const content = `---
title: Test

date: 2024-01-15
---
Content`;

    const result = parseFrontmatter(content);

    expect(result.data.title).toBe('Test');
    expect(result.data.date).toBe('2024-01-15');
  });
});
