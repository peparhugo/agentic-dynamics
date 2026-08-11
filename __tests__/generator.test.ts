import fs from 'fs';
import path from 'path';
import {
  parseMarkdownFile,
  readContentDirectory,
  generateSite,
} from '../src/generator';

const tmpDir = path.join(__dirname, '..', '.test-tmp');

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

function createContentDir(name: string): string {
  const dir = path.join(tmpDir, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('parseMarkdownFile', () => {
  it('parses markdown with frontmatter', () => {
    const contentDir = createContentDir('parse-test');
    const filePath = writeFile(
      contentDir,
      'hello.md',
      `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - ssg
---

# Hello

This is a paragraph.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('Hello World');
    expect(page!.date).toBe('2024-01-15');
    expect(page!.tags).toEqual(['typescript', 'ssg']);
    expect(page!.slug).toBe('hello');
    expect(page!.content).toContain('<h1');
    expect(page!.content).toContain('Hello');
    expect(page!.content).toContain('This is a paragraph.');
  });

  it('uses filename as title when no title in frontmatter', () => {
    const contentDir = createContentDir('no-title');
    const filePath = writeFile(
      contentDir,
      'about.md',
      `# About

Some content.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('about');
    expect(page!.slug).toBe('about');
    expect(page!.date).toBe('');
    expect(page!.tags).toEqual([]);
  });

  it('parses markdown with only frontmatter title', () => {
    const contentDir = createContentDir('title-only');
    const filePath = writeFile(
      contentDir,
      'test.md',
      `---
title: Just Title
---

Content here.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('Just Title');
    expect(page!.date).toBe('');
    expect(page!.tags).toEqual([]);
  });

  it('handles code blocks in markdown', () => {
    const contentDir = createContentDir('code-block');
    const filePath = writeFile(
      contentDir,
      'code.md',
      `---
title: Code Post
---

\`\`\`typescript
const x = 1;
\`\`\``
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.content).toContain('class="language-typescript"');
  });

  it('handles empty frontmatter gracefully', () => {
    const contentDir = createContentDir('empty-fm');
    const filePath = writeFile(
      contentDir,
      'empty.md',
      `---
---

Just content.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('empty');
    expect(page!.date).toBe('');
    expect(page!.tags).toEqual([]);
  });
});

describe('readContentDirectory', () => {
  it('returns empty array for non-existent directory', () => {
    const pages = readContentDirectory('/nonexistent/path');
    expect(pages).toEqual([]);
  });

  it('returns empty array for empty directory', () => {
    const contentDir = createContentDir('empty-dir');
    const pages = readContentDirectory(contentDir);
    expect(pages).toEqual([]);
  });

  it('reads all .md files in directory', () => {
    const contentDir = createContentDir('multi-file');
    writeFile(
      contentDir,
      'post1.md',
      `---
title: Post One
---

# One`
    );
    writeFile(
      contentDir,
      'post2.md',
      `---
title: Post Two
---

# Two`
    );
    writeFile(contentDir, 'not-a-post.txt', 'hello');

    const pages = readContentDirectory(contentDir);
    expect(pages).toHaveLength(2);
    expect(pages.map((p) => p.title)).toContain('Post One');
    expect(pages.map((p) => p.title)).toContain('Post Two');
  });

  it('skips non-markdown files', () => {
    const contentDir = createContentDir('skip-non-md');
    writeFile(contentDir, 'data.json', '{}');
    writeFile(contentDir, 'readme.md', `---
title: Readme
---

# Readme`);

    const pages = readContentDirectory(contentDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].title).toBe('Readme');
  });
});

describe('generateSite', () => {
  it('generates html files in output directory', () => {
    const contentDir = createContentDir('gen-site');
    const outputDir = path.join(tmpDir, 'gen-output');

    writeFile(
      contentDir,
      'post1.md',
      `---
title: First Post
date: 2024-01-01
tags:
  - blog
  - tech
---

# Hello

World content.`
    );

    writeFile(
      contentDir,
      'post2.md',
      `---
title: Second Post
date: 2024-02-01
tags:
  - tutorial
---

# Second

More content.`
    );

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(3);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'post1.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'post2.html'))).toBe(true);

    const post1Html = fs.readFileSync(path.join(outputDir, 'post1.html'), 'utf-8');
    expect(post1Html).toContain('<!DOCTYPE html>');
    expect(post1Html).toContain('<title>First Post</title>');
    expect(post1Html).toContain('>Hello</h1>');
    expect(post1Html).toContain('World content.');
    expect(post1Html).toContain('2024-01-01');
    expect(post1Html).toContain('blog, tech');

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('post1.html');
    expect(indexHtml).toContain('post2.html');
  });

  it('handles empty content directory', () => {
    const contentDir = createContentDir('empty-gen');
    const outputDir = path.join(tmpDir, 'empty-output');

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(0);
  });

  it('creates output directory if it does not exist', () => {
    const contentDir = createContentDir('create-dir-test');
    const outputDir = path.join(tmpDir, 'new-output-dir');

    writeFile(
      contentDir,
      'hello.md',
      `---
title: Hello
---

Hello world.`
    );

    expect(fs.existsSync(outputDir)).toBe(false);
    generateSite(contentDir, outputDir);
    expect(fs.existsSync(outputDir)).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
  });

  it('generates page with no tags', () => {
    const contentDir = createContentDir('no-tags');
    const outputDir = path.join(tmpDir, 'no-tags-output');

    writeFile(
      contentDir,
      'simple.md',
      `---
title: Simple Page
---

Simple content.`
    );

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(2);

    const simpleHtml = fs.readFileSync(path.join(outputDir, 'simple.html'), 'utf-8');
    expect(simpleHtml).toContain('<title>Simple Page</title>');
    expect(simpleHtml).toContain('<h1>Simple Page</h1>');
    expect(simpleHtml).toContain('<p>Simple content.</p>');
  });
});

describe('index.html generation', () => {
  it('includes links to all pages', () => {
    const contentDir = createContentDir('index-test');
    const outputDir = path.join(tmpDir, 'index-output');

    writeFile(
      contentDir,
      'a.md',
      `---
title: Page A
date: 2024-03-01
tags:
  - alpha
---

Content A.`
    );

    writeFile(
      contentDir,
      'b.md',
      `---
title: Page B
---

Content B.`
    );

    generateSite(contentDir, outputDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<a href="a.html">Page A</a>');
    expect(indexHtml).toContain('<a href="b.html">Page B</a>');
  });
});
