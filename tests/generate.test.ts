import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, listMarkdownFiles } from '../src/generate';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('listMarkdownFiles', () => {
  it('finds markdown files recursively, ignoring non-markdown files', async () => {
    const content = await makeTempDir();
    await fs.mkdir(path.join(content, 'nested'));
    await fs.writeFile(path.join(content, 'a.md'), 'a');
    await fs.writeFile(path.join(content, 'b.txt'), 'b');
    await fs.writeFile(path.join(content, 'nested', 'c.md'), 'c');

    const files = (await listMarkdownFiles(content)).sort();
    expect(files).toEqual([
      path.join(content, 'a.md'),
      path.join(content, 'nested', 'c.md'),
    ]);
  });
});

describe('buildSite', () => {
  it('generates index.html and one page per markdown file', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();

    await fs.writeFile(
      path.join(content, 'hello.md'),
      `---
title: Hello World
date: 2024-01-02
tags: [intro, demo]
---
# Welcome

Some text.
`
    );
    await fs.writeFile(path.join(content, 'second.md'), '# No frontmatter\n\nJust a body.');

    const result = await buildSite(content, output);

    expect(result.pages).toHaveLength(2);
    expect(result.pages.map((p) => p.slug).sort()).toEqual(['hello', 'second']);

    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('Hello World');
    expect(index).toContain('Second');
    expect(index).toContain('hello.html');
    expect(index).toContain('second.html');
    expect(index).toContain('2024-01-02');
    expect(index).toContain('intro');

    const hello = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(hello).toContain('<title>Hello World</title>');
    expect(hello).toContain('<h1>Welcome</h1>');
    expect(hello).toContain('intro');
    expect(hello).toContain('2024-01-02');
    // The frontmatter delimiter must not leak through as a horizontal rule.
    expect(hello).not.toContain('<hr');

    const second = await fs.readFile(path.join(output, 'second.html'), 'utf8');
    expect(second).toContain('<h1>No frontmatter</h1>');
  });

  it('preserves nested directory structure', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();

    await fs.mkdir(path.join(content, 'guides'));
    await fs.writeFile(path.join(content, 'guides', 'intro.md'), '# Intro');

    await buildSite(content, output);

    const page = await fs.readFile(path.join(output, 'guides', 'intro.html'), 'utf8');
    expect(page).toContain('<h1>Intro</h1>');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('guides/intro.html');
  });

  it('sorts pages by date descending', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();

    await fs.writeFile(path.join(content, 'old.md'), '---\ntitle: Old\ndate: 2020-01-01\n---\nOld');
    await fs.writeFile(path.join(content, 'new.md'), '---\ntitle: New\ndate: 2024-01-01\n---\nNew');
    await fs.writeFile(path.join(content, 'undated.md'), '# Undated');

    const result = await buildSite(content, output);

    expect(result.pages.map((p) => p.title)).toEqual(['New', 'Old', 'Undated']);
  });

  it('falls back to a title derived from the file name', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();

    await fs.writeFile(path.join(content, 'my-first-post.md'), '# Hello');

    const result = await buildSite(content, output);

    expect(result.pages[0].title).toBe('My First Post');
  });
});
