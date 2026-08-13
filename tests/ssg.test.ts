import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runCli } from '../src/cli';
import { buildSite } from '../src';

describe('static site generator', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'public');
    await fs.mkdir(contentDir);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('renders Markdown and frontmatter into a page', async () => {
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: A <Great> Post
date: 2026-08-13
tags: [typescript, static sites]
---

## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(html).toContain('<title>A &lt;Great&gt; Post</title>');
    expect(html).toContain('<h2>Welcome</h2>');
    expect(html).toContain('<strong>important</strong>');
    expect(html).toContain('<time datetime="2026-08-13">2026-08-13</time>');
    expect(html).toContain('<li>typescript</li>');
  });

  test('generates an index sorted by date and links nested pages', async () => {
    await fs.mkdir(path.join(contentDir, 'notes'));
    await fs.writeFile(path.join(contentDir, 'older.md'), '---\ntitle: Older\ndate: 2025-01-01\n---\nOld');
    await fs.writeFile(path.join(contentDir, 'notes', 'new post.md'), '---\ntitle: Newer\ndate: 2026-01-01\n---\nNew');

    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    const nested = await fs.readFile(path.join(outputDir, 'notes', 'new post.html'), 'utf8');

    expect(index).toContain('href="notes/new%20post.html"');
    expect(index.indexOf('Newer')).toBeLessThan(index.indexOf('Older'));
    expect(nested).toContain('<p>New</p>');
  });

  test('uses the filename as a title when frontmatter has no title', async () => {
    await fs.writeFile(path.join(contentDir, 'about-us.md'), 'About us');

    await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'about-us.html'), 'utf8');

    expect(html).toContain('<h1>About Us</h1>');
  });

  test('generates an empty index when there are no pages', async () => {
    const pages = await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toEqual([]);
    expect(index).toContain('<h1>Pages</h1>');
  });

  test('reports a missing content directory', async () => {
    await expect(buildSite({
      contentDir: path.join(root, 'missing'),
      outputDir
    })).rejects.toThrow('Content directory does not exist');
  });

  test('runs build with custom CLI directories', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    const exitCode = await runCli(
      ['build', '--content', contentDir, '--output', outputDir],
      { stdout, stderr }
    );

    expect(exitCode).toBe(0);
    expect(stdout.write).toHaveBeenCalledWith('Generated 1 page.\n');
    expect(stderr.write).not.toHaveBeenCalled();
    await expect(fs.stat(path.join(outputDir, 'page.html'))).resolves.toBeDefined();
  });

  test('rejects invalid CLI input', async () => {
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    await expect(runCli([], { stdout, stderr })).resolves.toBe(1);
    await expect(runCli(['build', '--other'], { stdout, stderr })).resolves.toBe(1);
    expect(stderr.write).toHaveBeenCalledTimes(2);
  });
});
