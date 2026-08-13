import { parseFrontmatter } from './frontmatter';

describe('Frontmatter Parser', () => {
  it('should parse valid YAML frontmatter', () => {
    const markdown = `---
title: Hello World
date: 2023-01-01
tags: [javascript, typescript]
---
# Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.title).toBe('Hello World');
    expect(result.frontmatter.date).toBe('2023-01-01');
    expect(result.frontmatter.tags).toEqual(['javascript', 'typescript']);
    expect(result.content).toBe('# Content');
  });

  it('should handle markdown without frontmatter', () => {
    const markdown = '# Just a heading\n\nSome content';

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter).toEqual({});
    expect(result.content).toBe('# Just a heading\n\nSome content');
  });

  it('should parse boolean values', () => {
    const markdown = `---
title: Test
published: true
draft: false
---
Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.published).toBe(true);
    expect(result.frontmatter.draft).toBe(false);
  });

  it('should parse numeric values', () => {
    const markdown = `---
title: Test
count: 42
rating: 3.5
---
Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.count).toBe(42);
    expect(result.frontmatter.rating).toBe(3.5);
  });

  it('should parse quoted strings', () => {
    const markdown = `---
title: "My Title"
description: "A longer description"
---
Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.title).toBe('My Title');
    expect(result.frontmatter.description).toBe('A longer description');
  });

  it('should parse arrays with mixed types', () => {
    const markdown = `---
tags: [tag1, tag2, tag3]
numbers: [1, 2, 3]
---
Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.tags).toEqual(['tag1', 'tag2', 'tag3']);
    expect(result.frontmatter.numbers).toEqual(['1', '2', '3']);
  });

  it('should handle missing frontmatter end marker', () => {
    const markdown = `---
title: Test
no closing marker
# Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter).toEqual({});
    expect(result.content).toBe(`---
title: Test
no closing marker
# Content`);
  });

  it('should handle empty frontmatter', () => {
    const markdown = `---
---
# Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter).toEqual({});
    expect(result.content).toBe('# Content');
  });

  it('should ignore YAML comments', () => {
    const markdown = `---
title: Test
# this is a comment
author: John
---
Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.title).toBe('Test');
    expect(result.frontmatter.author).toBe('John');
    expect(result.frontmatter['# this is a comment']).toBeUndefined();
  });

  it('should handle null values', () => {
    const markdown = `---
title: Test
empty: null
---
Content`;

    const result = parseFrontmatter(markdown);

    expect(result.frontmatter.empty).toBeNull();
  });

  it('should trim content properly', () => {
    const markdown = `---
title: Test
---

# Content with leading blank line
More content`;

    const result = parseFrontmatter(markdown);

    expect(result.content).toBe('# Content with leading blank line\nMore content');
  });
});
