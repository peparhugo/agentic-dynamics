import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import {
  buildSite,
  slugFromSource,
  titleFromSource,
  collectMarkdownFiles,
} from '../build';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

async function write(filePath: string, content: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, 'utf-8');
}

describe('slugFromSource', () => {
  it('maps a relative path to a html slug', () => {
    expect(slugFromSource('hello-world.md')).toBe('hello-world');
    expect(slugFromSource('posts/my first post.markdown')).toBe('posts/my-first-post');
    expect(slugFromSource('a/b/c.md')).toBe('a/b/c');
  });
});

describe('titleFromSource', () => {
  it('derives a readable title from a filename', () => {
    expect(titleFromSource('hello-world.md')).toBe('Hello World');
  });
});

describe('collectMarkdownFiles', () => {
  it('finds markdown files recursively and ignores non-markdown', async () => {
    const dir = await makeTempDir();
    await write(path.join(dir, 'a.md'), '# A');
    await write(path.join(dir, 'sub', 'b.markdown'), '# B');
    await write(path.join(dir, 'c.txt'), 'not markdown');
    await write(path.join(dir, 'notes.md~'), 'backup');

    const files = await collectMarkdownFiles(dir);
    expect(files.sort()).toEqual(['a.md', 'sub/b.markdown']);
  });
});

describe('buildSite', () => {
  it('generates index.html and a page per markdown file', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    await write(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello World
date: 2024-03-01
tags: [intro, demo]
---
# Hello
Welcome to **the site**.
`
    );
    await write(
      path.join(contentDir, 'posts', 'second.md'),
      `---
title: Second Post
date: 2024-01-01
tags: [blog]
---
Some *second* content.
`
    );

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(2);

    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('<h1>Pages</h1>');
    expect(index).toContain('href="hello.html"');
    expect(index).toContain('Hello World');
    expect(index).toContain('href="posts/second.html"');
    expect(index).toContain('Second Post');

    const hello = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(hello).toContain('<title>Hello World</title>');
    expect(hello).toContain('<h1>Hello World</h1>');
    expect(hello).toContain('<strong>the site</strong>');
    expect(hello).toContain('class="tag">intro');
    expect(hello).toContain('href="index.html"');

    const second = await fs.readFile(
      path.join(outputDir, 'posts', 'second.html'),
      'utf-8'
    );
    expect(second).toContain('Second Post');
  });

  it('sorts the index by date (newest first) and falls back to title', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    await write(path.join(contentDir, 'older.md'), '---\ndate: 2020-01-01\n---\nOld');
    await write(path.join(contentDir, 'newer.md'), '---\ndate: 2025-01-01\n---\nNew');

    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
    const olderPos = index.indexOf('Older');
    const newerPos = index.indexOf('Newer');
    expect(newerPos).toBeLessThan(olderPos);
  });

  it('falls back to a filename-derived title when title is missing', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    await write(path.join(contentDir, 'no-title.md'), 'Just content.');

    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('No Title');
  });

  it('writes an empty index when there is no markdown content', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir, { recursive: true });

    const pages = await buildSite({ contentDir, outputDir });
    expect(pages).toEqual([]);

    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('No pages yet.');
  });

  it('recreates the output directory, removing stale files', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    await write(path.join(contentDir, 'one.md'), '---\ntitle: One\n---\nBody');
    await fs.mkdir(outputDir, { recursive: true });
    await write(path.join(outputDir, 'stale.html'), 'old');

    await buildSite({ contentDir, outputDir });

    await expect(
      fs.readFile(path.join(outputDir, 'stale.html'), 'utf-8')
    ).rejects.toThrow();
    await expect(
      fs.readFile(path.join(outputDir, 'one.html'), 'utf-8')
    ).resolves.toContain('One');
  });
});
