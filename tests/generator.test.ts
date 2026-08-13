import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

describe('buildSite', () => {
  let temporaryDirectory: string;

  beforeEach(async () => {
    temporaryDirectory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(temporaryDirectory, { recursive: true, force: true });
  });

  it('renders Markdown and frontmatter into pages and an index', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello <World>
date: 2025-02-03
tags:
  - news
  - typescript
---
# Welcome

This is **static**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toEqual([expect.objectContaining({
      title: 'Hello <World>',
      date: '2025-02-03',
      tags: ['news', 'typescript'],
      url: 'hello.html',
    })]);
    expect(page).toContain('<title>Hello &lt;World&gt;</title>');
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>static</strong>');
    expect(page).toContain('<li>typescript</li>');
    expect(index).toContain('<a href="hello.html">Hello &lt;World&gt;</a>');
  });

  it('preserves nested paths and falls back to the filename for a title', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(path.join(contentDir, 'notes'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'notes', 'first.md'), 'A paragraph.');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages[0]).toEqual(expect.objectContaining({ title: 'first', url: 'notes/first.html' }));
    await expect(fs.readFile(path.join(outputDir, 'notes', 'first.html'), 'utf8'))
      .resolves.toContain('<p>A paragraph.</p>');
  });

  it('creates an empty index and removes stale output', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(contentDir);
    await fs.mkdir(outputDir);
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'stale');

    await expect(buildSite({ contentDir, outputDir })).resolves.toEqual([]);
    await expect(fs.stat(path.join(outputDir, 'stale.html'))).rejects.toThrow();
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('<h1>Pages</h1>');
  });
});
