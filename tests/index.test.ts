import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/index';

describe('buildSite', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('renders Markdown, frontmatter, and an index', async () => {
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2024-04-03
tags: [news, typescript]
---
## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toEqual([expect.objectContaining({
      title: 'Hello World',
      date: '2024-04-03',
      tags: ['news', 'typescript'],
      url: '/hello.html'
    })]);
    expect(page).toContain('<h2>Welcome</h2>');
    expect(page).toContain('<strong>important</strong>');
    expect(page).toContain('<li>typescript</li>');
    expect(index).toContain('<a href="/hello.html">Hello World</a>');
  });

  it('supports nested content and derives a title when absent', async () => {
    await fs.mkdir(path.join(contentDir, 'guides'));
    await fs.writeFile(path.join(contentDir, 'guides', 'start.md'), '# Start here');

    await buildSite({ contentDir, outputDir });

    const page = await fs.readFile(path.join(outputDir, 'guides', 'start.html'), 'utf8');
    expect(page).toContain('<title>start</title>');
    expect(page).toContain('<h1>Start here</h1>');
  });

  it('cleans stale output files when rebuilding', async () => {
    await fs.mkdir(outputDir);
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'old');
    await fs.writeFile(path.join(contentDir, 'page.md'), 'Current');

    await buildSite({ contentDir, outputDir });

    await expect(fs.stat(path.join(outputDir, 'stale.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  it('escapes frontmatter displayed in generated HTML', async () => {
    await fs.writeFile(path.join(contentDir, 'safe.md'), `---
title: <script>alert(1)</script>
tags: '<unsafe>'
---
Text
`);

    await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'safe.html'), 'utf8');

    expect(page).not.toContain('<script>');
    expect(page).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(page).toContain('&lt;unsafe&gt;');
  });
});
