import { parseMarkdown } from '../src/parser';

describe('Parser', () => {
  describe('parseMarkdown', () => {
    it('should parse markdown with YAML frontmatter', async () => {
      const content = `---
title: Test Page
date: 2024-01-15
tags: typescript, cli
---

# Hello World

This is a test.`;

      const result = await parseMarkdown(content);

      expect(result.frontmatter.title).toBe('Test Page');
      expect(result.frontmatter.date).toBe('2024-01-15');
      expect(result.frontmatter.tags).toEqual(['typescript', 'cli']);
      expect(result.content).toContain('# Hello World');
      expect(result.html).toContain('<h1>Hello World</h1>');
    });

    it('should handle markdown without frontmatter', async () => {
      const content = '# Simple Page\n\nJust content.';

      const result = await parseMarkdown(content);

      expect(result.frontmatter).toEqual({});
      expect(result.content).toContain('# Simple Page');
      expect(result.html).toContain('<h1>Simple Page</h1>');
    });

    it('should parse YAML with quoted values', async () => {
      const content = `---
title: "My Special Page"
date: "2024-12-25"
---

Content here.`;

      const result = await parseMarkdown(content);

      expect(result.frontmatter.title).toBe('My Special Page');
      expect(result.frontmatter.date).toBe('2024-12-25');
    });

    it('should handle multiple tags with whitespace', async () => {
      const content = `---
title: Tagged Post
tags: python, javascript, rust, go
---

Content.`;

      const result = await parseMarkdown(content);

      expect(result.frontmatter.tags).toEqual(['python', 'javascript', 'rust', 'go']);
    });

    it('should convert markdown to HTML', async () => {
      const content = `---
title: Markdown Test
---

# Heading

**Bold text** and *italic text*

- Item 1
- Item 2

\`\`\`
code block
\`\`\``;

      const result = await parseMarkdown(content);

      expect(result.html).toContain('<h1>Heading</h1>');
      expect(result.html).toContain('<strong>Bold text</strong>');
      expect(result.html).toContain('<em>italic text</em>');
      expect(result.html).toContain('<li>Item 1</li>');
      expect(result.html).toContain('<pre>');
      expect(result.html).toContain('<code>');
    });

    it('should handle empty tags', async () => {
      const content = `---
title: No Tags
tags:
---

Content.`;

      const result = await parseMarkdown(content);

      expect(result.frontmatter.tags).toEqual([]);
    });

    it('should preserve custom frontmatter fields', async () => {
      const content = `---
title: Custom Fields
author: John Doe
category: tutorial
---

Content.`;

      const result = await parseMarkdown(content);

      expect(result.frontmatter.title).toBe('Custom Fields');
      expect(result.frontmatter.author).toBe('John Doe');
      expect(result.frontmatter.category).toBe('tutorial');
    });
  });
});
