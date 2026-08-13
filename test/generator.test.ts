import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

describe('buildSite', () => {
  let root: string;
  let content: string;
  let output: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
    content = path.join(root, 'content');
    output = path.join(root, 'public');
    await fs.mkdir(content);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('renders Markdown, frontmatter, and an index ordered by date', async () => {
    await fs.writeFile(path.join(content, 'older.md'), `---
title: Older Post
date: 2024-01-01
tags: [news, typescript]
---
# Introduction

This is **important**.
`);
    await fs.writeFile(path.join(content, 'newer.md'), `---
title: Newer Post
date: 2024-03-01
tags: update, release
---
Latest post.
`);

    const pages = await buildSite({ content, output });
    const older = await fs.readFile(path.join(output, 'older.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');

    expect(pages.map((page) => page.title)).toEqual(['Newer Post', 'Older Post']);
    expect(older).toContain('<h1>Introduction</h1>');
    expect(older).toContain('<strong>important</strong>');
    expect(older).toContain('<span class="tag">typescript</span>');
    expect(index).toContain('<a href="newer.html">Newer Post</a>');
    expect(index.indexOf('Newer Post')).toBeLessThan(index.indexOf('Older Post'));
  });

  it('supports nested files, fallback titles, and cleans stale output', async () => {
    await fs.mkdir(path.join(content, 'guides'));
    await fs.writeFile(path.join(content, 'guides', 'start.md'), 'Hello *world*.');
    await fs.mkdir(output);
    await fs.writeFile(path.join(output, 'stale.html'), 'stale');

    await buildSite({ content, output });

    const generated = await fs.readFile(path.join(output, 'guides', 'start.html'), 'utf8');
    await expect(fs.stat(path.join(output, 'stale.html'))).rejects.toThrow();
    expect(generated).toContain('<title>start</title>');
    expect(generated).toContain('<em>world</em>');
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('guides/start.html');
  });

  it('escapes frontmatter rendered into HTML', async () => {
    await fs.writeFile(path.join(content, 'safe.md'), `---
title: '<script>alert(1)</script>'
tags: ['<unsafe>']
---
Body
`);

    await buildSite({ content, output });
    const generated = await fs.readFile(path.join(output, 'safe.html'), 'utf8');

    expect(generated).not.toContain('<script>');
    expect(generated).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(generated).toContain('&lt;unsafe&gt;');
  });

  it('generates an empty index when no Markdown files exist', async () => {
    await fs.writeFile(path.join(content, 'ignored.txt'), 'not Markdown');
    await expect(buildSite({ content, output })).resolves.toEqual([]);
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('<h1>Pages</h1>');
  });

  it('refuses to overwrite the content directory', async () => {
    await fs.writeFile(path.join(content, 'keep.md'), 'Do not delete');
    await expect(buildSite({ content, output: content })).rejects.toThrow(
      'Content and output directories must be different',
    );
    await expect(fs.readFile(path.join(content, 'keep.md'), 'utf8')).resolves.toBe('Do not delete');
  });
});
