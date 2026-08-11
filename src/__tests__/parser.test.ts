import fs from 'fs';
import path from 'path';
import os from 'os';
import { parseMarkdownFiles } from '../parser';

describe('parseMarkdownFiles', () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function writeFile(name: string, content: string): void {
    fs.writeFileSync(path.join(tmpDir, name), content, 'utf-8');
  }

  it('returns an empty array for an empty directory', () => {
    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toEqual([]);
  });

  it('returns an empty array when directory has no .md files', () => {
    writeFile('notes.txt', 'hello');
    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toEqual([]);
  });

  it('parses a single markdown file with frontmatter', () => {
    writeFile('hello.md', `---
title: Hello World
date: 2024-01-01
tags:
  - js
  - ts
---
# Hello

This is a paragraph.`);

    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('hello');
    expect(pages[0].frontmatter.title).toBe('Hello World');
    expect(pages[0].frontmatter.date).toBe('2024-01-01');
    expect(pages[0].frontmatter.tags).toEqual(['js', 'ts']);
    expect(pages[0].html).toContain('<h1');
    expect(pages[0].html).toContain('Hello');
    expect(pages[0].html).toContain('paragraph');
  });

  it('parses multiple markdown files', () => {
    writeFile('a.md', `---
title: Alpha
date: '2024-01-01'
tags: []
---
Alpha content`);

    writeFile('b.md', `---
title: Beta
date: '2024-02-01'
tags: []
---
Beta content`);

    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toHaveLength(2);
    // sorted by title
    expect(pages[0].frontmatter.title).toBe('Alpha');
    expect(pages[1].frontmatter.title).toBe('Beta');
  });

  it('handles missing frontmatter fields gracefully', () => {
    writeFile('minimal.md', `---
title: Just Title
---
No date or tags`);

    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].frontmatter.date).toBe('');
    expect(pages[0].frontmatter.tags).toEqual([]);
  });

  it('handles no frontmatter at all', () => {
    writeFile('plain.md', `# Just Content

Some text.`);

    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].frontmatter.title).toBe('');
    expect(pages[0].frontmatter.date).toBe('');
    expect(pages[0].frontmatter.tags).toEqual([]);
    expect(pages[0].html).toContain('<h1');
  });

  it('ignores non-markdown files', () => {
    writeFile('hello.md', `---
title: Hello
date: '2024-01-01'
tags: []
---
Hello`);

    writeFile('readme.txt', 'not markdown');
    writeFile('image.png', 'fake binary');

    const pages = parseMarkdownFiles(tmpDir);
    expect(pages).toHaveLength(1);
  });

  it('converts markdown to HTML correctly', () => {
    writeFile('formatting.md', `---
title: Format Test
date: '2024-01-01'
tags: []
---
# Heading

**Bold** and *italic*.

- List item 1
- List item 2

\`inline code\``);

    const pages = parseMarkdownFiles(tmpDir);
    expect(pages[0].html).toContain('<h1');
    expect(pages[0].html).toContain('<strong>Bold</strong>');
    expect(pages[0].html).toContain('<em>italic</em>');
    expect(pages[0].html).toContain('<li>List item 1</li>');
    expect(pages[0].html).toContain('<code>inline code</code>');
  });
});
