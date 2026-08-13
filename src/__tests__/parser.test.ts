import { parseMarkdown } from '../parser';

describe('parser', () => {
  describe('parseMarkdown', () => {
    it('should parse simple markdown without frontmatter', async () => {
      const content = '# Hello World\n\nThis is a test.';
      const result = await parseMarkdown(content, 'test');

      expect(result.slug).toBe('test');
      expect(result.frontmatter.title).toBe('Untitled');
      expect(result.html).toContain('<h1>Hello World</h1>');
      expect(result.html).toContain('<p>This is a test.</p>');
    });

    it('should parse markdown with frontmatter', async () => {
      const content = `---
title: My Post
date: "2024-01-15"
tags:
  - typescript
  - testing
---

# Content

This is the body.`;
      const result = await parseMarkdown(content, 'my-post');

      expect(result.slug).toBe('my-post');
      expect(result.frontmatter.title).toBe('My Post');
      expect(result.frontmatter.date).toBe('2024-01-15');
      expect(result.frontmatter.tags).toEqual(['typescript', 'testing']);
      expect(result.html).toContain('<h1>Content</h1>');
      expect(result.html).toContain('<p>This is the body.</p>');
    });

    it('should handle markdown with headings and lists', async () => {
      const content = `---
title: Test Post
---

## Section

- Item 1
- Item 2
- Item 3`;
      const result = await parseMarkdown(content, 'test-post');

      expect(result.frontmatter.title).toBe('Test Post');
      expect(result.html).toContain('<h2>Section</h2>');
      expect(result.html).toContain('<li>Item 1</li>');
      expect(result.html).toContain('<li>Item 2</li>');
      expect(result.html).toContain('<li>Item 3</li>');
    });

    it('should handle markdown with code blocks', async () => {
      const content = `---
title: Code Example
---

\`\`\`typescript
const x = 42;
\`\`\``;
      const result = await parseMarkdown(content, 'code');

      expect(result.frontmatter.title).toBe('Code Example');
      expect(result.html).toContain('<pre><code');
      expect(result.html).toContain('const x = 42;');
    });

    it('should preserve custom frontmatter properties', async () => {
      const content = `---
title: Test
author: John Doe
category: tech
---

Content`;
      const result = await parseMarkdown(content, 'test');

      expect(result.frontmatter.author).toBe('John Doe');
      expect(result.frontmatter.category).toBe('tech');
    });

    it('should handle empty tags', async () => {
      const content = `---
title: Test
---

Content`;
      const result = await parseMarkdown(content, 'test');

      expect(result.frontmatter.tags).toEqual([]);
    });
  });
});
