import { processMarkdownFile } from './page';

describe('processMarkdownFile', () => {
  it('should extract title from frontmatter', async () => {
    const content = `---
title: My First Post
---
# Content`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.title).toBe('My First Post');
  });

  it('should generate title from slug if not in frontmatter', async () => {
    const content = '# Content';

    const page = await processMarkdownFile('my-first-post.md', content);

    expect(page.title).toBe('My First Post');
  });

  it('should extract date from frontmatter', async () => {
    const content = `---
title: Post
date: 2024-01-15
---
Content`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.date).toBe('2024-01-15');
  });

  it('should extract tags from frontmatter', async () => {
    const content = `---
title: Post
tags: [javascript, testing, cli]
---
Content`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.tags).toEqual(['javascript', 'testing', 'cli']);
  });

  it('should convert markdown to HTML', async () => {
    const content = `---
title: Post
---
# Heading

This is **bold** text.`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.html).toContain('<h1>Heading</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
  });

  it('should set slug from filename', async () => {
    const content = 'Content';

    const page = await processMarkdownFile('my-post.md', content);

    expect(page.slug).toBe('my-post');
  });

  it('should handle no tags', async () => {
    const content = `---
title: Post
---
Content`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.tags).toBeUndefined();
  });

  it('should preserve additional frontmatter fields', async () => {
    const content = `---
title: Post
author: John Doe
category: Tech
---
Content`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.author).toBe('John Doe');
    expect(page.category).toBe('Tech');
  });

  it('should handle complex markdown', async () => {
    const content = `---
title: Complex
---
# Header

- List item 1
- List item 2

\`\`\`javascript
const x = 1;
\`\`\`

[Link](https://example.com)`;

    const page = await processMarkdownFile('test.md', content);

    expect(page.html).toContain('<ul>');
    expect(page.html).toContain('List item 1');
    expect(page.html).toContain('<a href="https://example.com">Link</a>');
  });

  it('should handle empty frontmatter', async () => {
    const content = `---
---
# Default Title
Content`;

    const page = await processMarkdownFile('some-title.md', content);

    expect(page.title).toBe('Some Title');
    expect(page.slug).toBe('some-title');
  });
});
