import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
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

  it('renders Markdown and frontmatter into page and index files', async () => {
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2024-05-01
tags:
  - news
  - typescript
---
# Welcome

This is **generated**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toMatchObject([{ title: 'Hello World', date: '2024-05-01', tags: ['news', 'typescript'] }]);
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>generated</strong>');
    expect(page).toContain('news, typescript');
    expect(index).toContain('<a href="hello.html">Hello World</a>');
  });

  it('preserves nested paths, ignores non-Markdown files, and uses filename titles', async () => {
    await fs.mkdir(path.join(contentDir, 'guides'));
    await fs.writeFile(path.join(contentDir, 'guides', 'start.md'), 'Start here.');
    await fs.writeFile(path.join(contentDir, 'ignored.txt'), 'Not content.');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(1);
    expect(pages[0]).toMatchObject({ title: 'start', url: 'guides/start.html' });
    await expect(fs.readFile(path.join(outputDir, 'guides', 'start.html'), 'utf8')).resolves.toContain('<p>Start here.</p>');
    await expect(fs.access(path.join(outputDir, 'ignored.html'))).rejects.toThrow();
  });

  it('creates an index when the content directory is empty', async () => {
    await buildSite({ contentDir, outputDir });
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('No pages found.');
  });
});
