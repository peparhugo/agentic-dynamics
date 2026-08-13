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

  test('renders frontmatter, Markdown, and an index', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'public');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'hello.md'), `---
title: Hello World
date: 2024-01-02
tags: [news, welcome]
---
This is **important**.
`);

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');

    expect(pages).toEqual([expect.objectContaining({
      title: 'Hello World',
      date: '2024-01-02',
      tags: ['news', 'welcome'],
      url: 'hello.html',
    })]);
    expect(page).toContain('<strong>important</strong>');
    expect(page).toContain('<title>Hello World</title>');
    expect(page).toContain('Tags: news, welcome');
    expect(index).toContain('<a href="hello.html">Hello World</a>');
  });

  test('supports nested pages, title fallback, and cleans stale output', async () => {
    const content = path.join(root, 'articles');
    const output = path.join(root, 'site');
    await fs.mkdir(path.join(content, 'guides'), { recursive: true });
    await fs.mkdir(output);
    await fs.writeFile(path.join(content, 'guides', 'start.md'), '# Start');
    await fs.writeFile(path.join(content, 'ignore.txt'), 'not a page');
    await fs.writeFile(path.join(output, 'stale.html'), 'old');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages).toHaveLength(1);
    expect(pages[0]).toEqual(expect.objectContaining({ title: 'start', url: 'guides/start.html' }));
    await expect(fs.readFile(path.join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<h1>Start</h1>');
    await expect(fs.stat(path.join(output, 'stale.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test('escapes frontmatter inserted into HTML', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'safe.md'), '---\ntitle: "<script>alert(1)</script>"\n---\nText');

    await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'safe.html'), 'utf8');

    expect(page).not.toContain('<script>');
    expect(page).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  test('rejects paths that could overwrite content or the generated index', async () => {
    const content = path.join(root, 'site', 'content');
    await fs.mkdir(content, { recursive: true });
    await fs.writeFile(path.join(content, 'post.md'), 'Post');

    await expect(buildSite({ contentDir: content, outputDir: path.dirname(content) }))
      .rejects.toThrow('must not overlap');

    const separateOutput = path.join(root, 'output');
    await fs.writeFile(path.join(content, 'index.md'), 'Index content');
    await expect(buildSite({ contentDir: content, outputDir: separateOutput }))
      .rejects.toThrow('index.md conflicts');
  });
});
