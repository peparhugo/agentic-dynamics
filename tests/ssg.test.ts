import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('converts Markdown and frontmatter into a page', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2024-06-01
tags: [news, launch]
---
## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(pages).toEqual([{
      title: 'Hello World',
      date: '2024-06-01',
      tags: ['news', 'launch'],
      outputPath: 'hello.html'
    }]);
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<h2>Welcome</h2>');
    expect(html).toContain('<strong>important</strong>');
    expect(html).toContain('<li>news</li>');
  });

  test('generates an index ordered by newest dated page first', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'old.md'), '---\ntitle: Old\ndate: 2020-01-01\n---\nOld');
    await fs.writeFile(path.join(contentDir, 'new.md'), '---\ntitle: New\ndate: 2025-01-01\n---\nNew');

    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(index).toContain('<a href="new.html">New</a>');
    expect(index.indexOf('New</a>')).toBeLessThan(index.indexOf('Old</a>'));
  });

  test('uses the filename as a title and supports comma-separated tags', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'about.md'), '---\ntags: company, team\n---\nAbout us');

    const [page] = await buildSite({ contentDir, outputDir });

    expect(page).toMatchObject({ title: 'about', tags: ['company', 'team'] });
  });

  test('preserves nested paths and ignores non-Markdown files', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(path.join(contentDir, 'posts'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'posts', 'entry.md'), '# Entry');
    await fs.writeFile(path.join(contentDir, 'notes.txt'), 'Not a page');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(1);
    await expect(fs.readFile(path.join(outputDir, 'posts', 'entry.html'), 'utf8')).resolves.toContain('<h1>Entry</h1>');
    await expect(fs.stat(path.join(outputDir, 'notes.html'))).rejects.toThrow();
  });

  test('escapes frontmatter rendered into HTML', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'safe.md'), '---\ntitle: "<script>alert(1)</script>"\n---\nSafe');

    await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'safe.html'), 'utf8');

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).not.toContain('<script>');
  });
});
