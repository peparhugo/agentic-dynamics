import { describe, it, expect } from 'vitest';
import { parseMarkdownFile } from '../src/parser';
import fs from 'fs';
import path from 'path';
import os from 'os';

function createTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

function createFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  const dirPath = path.dirname(filePath);
  fs.mkdirSync(dirPath, { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('frontmatter parsing', () => {
  it('parses title from frontmatter', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: My Test Page
---
Content here.`);

    const page = parseMarkdownFile(file, dir);
    expect(page.frontmatter.title).toBe('My Test Page');
    expect(page.html).toContain('Content here.');
    fs.rmSync(dir, { recursive: true });
  });

  it('falls back to filename when no title in frontmatter', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'my-post.md', `---
tags: [misc]
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.frontmatter.title).toBe('my-post');
    fs.rmSync(dir, { recursive: true });
  });

  it('parses date from frontmatter', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
date: 2024-01-15
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.frontmatter.date).toBe('2024-01-15');
    fs.rmSync(dir, { recursive: true });
  });

  it('parses tags as YAML array', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
tags: [javascript, "typescript"]
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.tags).toEqual(['javascript', 'typescript']);
    fs.rmSync(dir, { recursive: true });
  });

  it('parses tags as comma-separated string', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
tags: javascript, typescript, css
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.tags).toEqual(['javascript', 'typescript', 'css']);
    fs.rmSync(dir, { recursive: true });
  });

  it('returns empty array for missing tags', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.tags).toEqual([]);
    fs.rmSync(dir, { recursive: true });
  });

  it('detects draft: true', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
draft: true
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.isDraft).toBe(true);
    fs.rmSync(dir, { recursive: true });
  });

  it('draft defaults to false', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.isDraft).toBe(false);
    fs.rmSync(dir, { recursive: true });
  });

  it('draft: false is recognized', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
draft: false
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.isDraft).toBe(false);
    fs.rmSync(dir, { recursive: true });
  });

  it('generates correct URL slug for root file', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.url).toBe('/test');
    fs.rmSync(dir, { recursive: true });
  });

  it('generates clean URL for index page', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'index.md', `---
title: Home
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.url).toBe('/');
    fs.rmSync(dir, { recursive: true });
  });

  it('generates nested URL for subdirectories', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'posts/hello-world.md', `---
title: Hello
---
Content`);

    const page = parseMarkdownFile(file, dir);
    expect(page.url).toBe('/posts/hello-world');
    fs.rmSync(dir, { recursive: true });
  });

  it('parses markdown to HTML', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
---
# Heading

Paragraph with **bold** text.`);

    const page = parseMarkdownFile(file, dir);
    expect(page.html).toContain('<h1');
    expect(page.html).toContain('<strong>bold</strong>');
    fs.rmSync(dir, { recursive: true });
  });

  it('applies syntax highlighting to code blocks', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'test.md', `---
title: Test
---
\`\`\`javascript
const x = 1;
\`\`\``);

    const page = parseMarkdownFile(file, dir);
    expect(page.html).toContain('hljs');
    expect(page.html).toContain('language-javascript');
    fs.rmSync(dir, { recursive: true });
  });

  it('handles no frontmatter at all', () => {
    const dir = createTempDir();
    const file = createFile(dir, 'plain.md', 'Just some content.');

    const page = parseMarkdownFile(file, dir);
    expect(page.frontmatter.title).toBe('plain');
    expect(page.isDraft).toBe(false);
    expect(page.tags).toEqual([]);
    expect(page.html).toContain('Just some content.');
    fs.rmSync(dir, { recursive: true });
  });
});
