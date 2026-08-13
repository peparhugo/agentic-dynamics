import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator.js';

describe('buildSite', () => {
  it('renders markdown pages and an index from frontmatter', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'public');
    await mkdir(content);
    await writeFile(path.join(content, 'hello.md'), `---
title: Hello <World>
date: 2025-01-02
  - news
  - updates
---
# Welcome

This is **markdown**.`);
    await writeFile(path.join(content, 'about.md'), '# About');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages.map((page) => page.slug)).toEqual(['hello', 'about']);
    const hello = await readFile(path.join(output, 'hello.html'), 'utf8');
    expect(hello).toContain('<title>Hello &lt;World&gt;</title>');
    expect(hello).toContain('<h1>Welcome</h1>');
    expect(hello).toContain('<strong>markdown</strong>');
    expect(hello).toContain('<li>news</li>');
    const index = await readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('<a href="hello.html">Hello &lt;World&gt;</a>');
    expect(index).toContain('<a href="about.html">about</a>');
  });
});
