import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createBuildEngine, type Plugin } from '../src';

const execFileAsync = promisify(execFile);

describe('incremental builds', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incremental-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('creates a manifest and skips unchanged pages while preserving page metadata', async () => {
    await fs.writeFile(path.join(contentDir, 'one.md'), '---\ntitle: One\n---\nFirst');
    await fs.writeFile(path.join(contentDir, 'two.md'), '---\ntitle: Two\n---\nSecond');
    const filesSeen: string[] = [];
    const plugin: Plugin = { onFile: (page) => { filesSeen.push(page.title); } };

    const first = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true, plugins: [plugin] });
    await first.build();
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await first.end();

    filesSeen.length = 0;
    const second = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true, plugins: [plugin] });
    const pages = await second.build();
    expect(second.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });
    expect(filesSeen).toEqual([]);
    expect(pages.map((page) => page.title)).toEqual(['One', 'Two']);
    await second.end();

    const manifest = JSON.parse(await fs.readFile(path.join(outputDir, '.ssg-cache.json'), 'utf8')) as { pages: object };
    expect(Object.keys(manifest.pages)).toEqual(['one.md', 'two.md']);
  });

  test('rebuilds only a changed source page', async () => {
    const one = path.join(contentDir, 'one.md');
    await fs.writeFile(one, '# One');
    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two');
    const first = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await first.build();
    await first.end();

    await fs.writeFile(one, '# One changed');
    const second = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await second.build();
    expect(second.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).resolves.toContain('One changed');
    await second.end();
  });

  test('invalidates every page when a template changes', async () => {
    await fs.writeFile(path.join(contentDir, 'one.md'), '# One');
    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two');
    const template = path.join(templatesDir, 'default.hbs');
    await fs.writeFile(template, '<main>{{{content}}}</main>');
    const first = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await first.build();
    await first.end();

    await fs.writeFile(template, '<article>{{{content}}}</article>');
    const second = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await second.build();
    expect(second.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).resolves.toContain('<article>');
    await second.end();
  });

  test('does a clean build without a cache and removes deleted page outputs', async () => {
    const removed = path.join(contentDir, 'removed.md');
    await fs.mkdir(outputDir);
    await fs.writeFile(path.join(outputDir, 'stale-before-cache.txt'), 'stale');
    await fs.writeFile(removed, '# Removed');
    const noCache = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await noCache.build();
    expect(noCache.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    await expect(fs.stat(path.join(outputDir, 'stale-before-cache.txt'))).rejects.toThrow();
    await noCache.end();

    await fs.rm(removed);
    const deletion = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await deletion.build();
    await expect(fs.stat(path.join(outputDir, 'removed.html'))).rejects.toThrow();
    await deletion.end();

    await fs.writeFile(path.join(contentDir, 'new.md'), '# New');
    await fs.writeFile(path.join(outputDir, 'stale.txt'), 'stale');
    const clean = await createBuildEngine({ contentDir, outputDir, templatesDir, incremental: true, clean: true });
    await clean.build();
    expect(clean.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    await expect(fs.stat(path.join(outputDir, 'stale.txt'))).rejects.toThrow();
    await clean.end();
  });

  test('CLI reports incremental build stats', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    const command = [path.resolve('lib/cli.js'), 'build', '--content', contentDir, '--output', outputDir,
      '--templates', templatesDir, '--incremental'];
    await execFileAsync(process.execPath, command);
    const result = await execFileAsync(process.execPath, command);

    expect(result.stdout).toContain('Build stats: 0 built, 1 skipped');
    expect(result.stdout).toMatch(/\d+ms elapsed, \d+ms saved/);
  });
});
