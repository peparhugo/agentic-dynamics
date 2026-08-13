import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/index';

describe('site generation', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('builds pages and an index with metadata and embedded HTML', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2026-08-13
tags:
  - news
  - typescript
---
# Welcome

<aside class="note">Raw HTML</aside>
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(page).toContain('<h1>Hello World</h1>');
    expect(page).toContain('<aside class="note">Raw HTML</aside>');
    expect(page).not.toContain('&lt;aside');
    expect(page).toContain('August 13, 2026');
    expect(page).toContain('news, typescript');
    expect(index).toContain('<a href="hello.html">Hello World</a>');
  });

  it('keeps the generated index separate from an index Markdown page', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'index.md'), '---\ntitle: Home article\n---\nHome');

    await buildSite({ contentDir, outputDir });

    await expect(fs.readFile(path.join(outputDir, 'index-page.html'), 'utf8')).resolves.toContain('Home article');
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('index-page.html');
  });
});
