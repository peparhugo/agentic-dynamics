import { execFile } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { buildSite } from '../src/generator';

const execFileAsync = promisify(execFile);

describe('buildSite', () => {
  it('renders frontmatter and Markdown pages with an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const contentDir = join(root, 'content');
    const outputDir = join(root, 'public');
    await mkdir(join(contentDir, 'guides'), { recursive: true });
    await writeFile(join(contentDir, 'welcome.md'), `---
title: Welcome <Home>
date: 2025-01-15
tags:
  - news
  - start
---
# Hello

This is **Markdown**.`);
    await writeFile(join(contentDir, 'guides', 'intro.md'), '# Introduction');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages.map((page) => page.outputPath)).toEqual(['guides/intro.html', 'welcome.html']);
    await expect(readFile(join(outputDir, 'welcome.html'), 'utf8')).resolves.toContain('<h1>Welcome &lt;Home&gt;</h1>');
    await expect(readFile(join(outputDir, 'welcome.html'), 'utf8')).resolves.toContain('<strong>Markdown</strong>');
    await expect(readFile(join(outputDir, 'guides', 'intro.html'), 'utf8')).resolves.toContain('<h1>guides/intro</h1>');
    const index = await readFile(join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('href="guides/intro.html"');
    expect(index).toContain('href="welcome.html"');
    expect(index).toContain('2025-01-15 | news, start');
  });

  it('cleans stale output and supports an empty content directory', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const contentDir = join(root, 'content');
    const outputDir = join(root, 'public');
    await mkdir(contentDir);
    await mkdir(outputDir);
    await writeFile(join(outputDir, 'stale.html'), 'old');

    await expect(buildSite({ contentDir, outputDir })).resolves.toEqual([]);
    await expect(readFile(join(outputDir, 'index.html'), 'utf8')).resolves.toContain('<ul></ul>');
    await expect(readFile(join(outputDir, 'stale.html'), 'utf8')).rejects.toThrow();
  });
});

describe('CLI', () => {
  it('builds using content and output overrides', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-cli-'));
    const contentDir = join(root, 'posts');
    const outputDir = join(root, 'site');
    await mkdir(contentDir);
    await writeFile(join(contentDir, 'post.md'), '---\ntitle: CLI page\n---\nContent');

    const { stdout } = await execFileAsync(process.execPath, [
      '-r',
      'ts-node/register',
      resolve('src/cli.ts'),
      'build',
      '--content', contentDir,
      '--output', outputDir
    ]);

    expect(stdout).toBe('Generated 1 page(s).\n');
    await expect(readFile(join(outputDir, 'post.html'), 'utf8')).resolves.toContain('<h1>CLI page</h1>');
  });
});
