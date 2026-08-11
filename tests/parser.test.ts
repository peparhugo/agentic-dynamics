import { parseMarkdownFile, parseMarkdownDirectory } from '../src/parser';
import fs from 'fs';
import path from 'path';

const testContentDir = path.join(__dirname, 'content');

function createTestContent(filename: string, content: string) {
  fs.mkdirSync(testContentDir, { recursive: true });
  fs.writeFileSync(path.join(testContentDir, filename), content, 'utf-8');
}

function cleanupTestContent() {
  if (fs.existsSync(testContentDir)) {
    fs.rmSync(testContentDir, { recursive: true, force: true });
  }
}

beforeEach(() => {
  cleanupTestContent();
  fs.mkdirSync(testContentDir, { recursive: true });
});

afterEach(() => {
  cleanupTestContent();
});

describe('parseMarkdownFile', () => {
  it('parses markdown with frontmatter correctly', () => {
    const md = `---
title: Hello World
date: 2024-01-15
tags:
  - javascript
  - ssg
---
# Heading

This is a paragraph.`;

    const filePath = path.join(testContentDir, 'hello.md');
    fs.writeFileSync(filePath, md, 'utf-8');

    const page = parseMarkdownFile(filePath);

    expect(page.frontmatter.title).toBe('Hello World');
    expect(page.frontmatter.date).toBe('2024-01-15');
    expect(page.frontmatter.tags).toEqual(['javascript', 'ssg']);
    expect(page.slug).toBe('hello');
    expect(page.html).toContain('<h1>Heading</h1>');
    expect(page.html).toContain('<p>This is a paragraph.</p>');
  });

  it('parses markdown without optional frontmatter fields', () => {
    const md = `---
title: Minimal
---
Just content.`;

    const filePath = path.join(testContentDir, 'minimal.md');
    fs.writeFileSync(filePath, md, 'utf-8');

    const page = parseMarkdownFile(filePath);

    expect(page.frontmatter.title).toBe('Minimal');
    expect(page.frontmatter.date).toBeUndefined();
    expect(page.frontmatter.tags).toBeUndefined();
    expect(page.slug).toBe('minimal');
  });

  it('throws on missing title', () => {
    const md = `---
date: 2024-01-01
---
No title here`;

    const filePath = path.join(testContentDir, 'notitle.md');
    fs.writeFileSync(filePath, md, 'utf-8');

    expect(() => parseMarkdownFile(filePath)).toThrow('Missing required frontmatter field "title"');
  });

  it('handles .markdown extension', () => {
    const md = `---
title: Markdown Ext
---
Content`;

    const filePath = path.join(testContentDir, 'ext.markdown');
    fs.writeFileSync(filePath, md, 'utf-8');

    const page = parseMarkdownFile(filePath);
    expect(page.slug).toBe('ext');
  });
});

describe('parseMarkdownDirectory', () => {
  it('reads all markdown files from directory', () => {
    createTestContent(
      'first.md',
      `---
title: First
date: 2024-03-01
---
First content`,
    );
    createTestContent(
      'second.md',
      `---
title: Second
date: 2024-01-01
---
Second content`,
    );

    const pages = parseMarkdownDirectory(testContentDir);
    expect(pages).toHaveLength(2);
    expect(pages[0].frontmatter.title).toBe('First');
    expect(pages[1].frontmatter.title).toBe('Second');
  });

  it('sorts pages by date in descending order', () => {
    createTestContent(
      'a.md',
      `---
title: Old
date: 2023-01-01
---
Old content`,
    );
    createTestContent(
      'b.md',
      `---
title: New
date: 2024-12-31
---
New content`,
    );
    createTestContent(
      'c.md',
      `---
title: Mid
date: 2024-06-15
---
Mid content`,
    );

    const pages = parseMarkdownDirectory(testContentDir);
    expect(pages[0].frontmatter.title).toBe('New');
    expect(pages[1].frontmatter.title).toBe('Mid');
    expect(pages[2].frontmatter.title).toBe('Old');
  });

  it('throws on non-existent directory', () => {
    expect(() => parseMarkdownDirectory('/nonexistent/path')).toThrow(
      'Content directory not found',
    );
  });

  it('skips non-markdown files', () => {
    createTestContent('page.md', `---\ntitle: Page\n---\nContent`);
    createTestContent('readme.txt', 'not markdown');

    const pages = parseMarkdownDirectory(testContentDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('page');
  });
});
