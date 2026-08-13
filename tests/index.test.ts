import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

describe('buildSite', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'public');
    await fs.mkdir(contentDir);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('renders Markdown and frontmatter into a page and index', async () => {
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello <World>
date: 2026-08-13
tags: [typescript, static sites]
---

## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(pages[0]).toMatchObject({
      title: 'Hello <World>',
      date: '2026-08-13',
      tags: ['typescript', 'static sites'],
      url: 'hello.html',
    });
    expect(page).toContain('<title>Hello &lt;World&gt;</title>');
    expect(page).toContain('<h2>Welcome</h2>');
    expect(page).toContain('<strong>important</strong>');
    expect(page).toContain('<li>static sites</li>');
    expect(index).toContain('<a href="hello.html">Hello &lt;World&gt;</a>');
    expect(index).toContain('datetime="2026-08-13"');
  });

  it('preserves nested paths and defaults missing titles to filenames', async () => {
    const nested = path.join(contentDir, 'guides');
    await fs.mkdir(nested);
    await fs.writeFile(path.join(nested, 'getting-started.MD'), '# Start');
    await fs.writeFile(path.join(contentDir, 'ignored.txt'), 'No page');

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'guides', 'getting-started.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(pages[0].title).toBe('getting-started');
    expect(pages[0].url).toBe('guides/getting-started.html');
    expect(page).toContain('<h1>getting-started</h1>');
  });

  it('accepts comma-separated tags and replaces stale output', async () => {
    await fs.mkdir(outputDir);
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'stale');
    await fs.writeFile(path.join(contentDir, 'post.md'), `---
tags: alpha, beta
---
Body`);

    const [page] = await buildSite({ contentDir, outputDir });

    expect(page.tags).toEqual(['alpha', 'beta']);
    await expect(fs.access(path.join(outputDir, 'stale.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  it('generates an empty index when there are no pages', async () => {
    const pages = await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toEqual([]);
    expect(index).toContain('<h1>Pages</h1>');
  });

  it('reports a missing content directory clearly', async () => {
    await expect(buildSite({
      contentDir: path.join(root, 'missing'),
      outputDir,
    })).rejects.toThrow('Content directory does not exist');
  });
});
