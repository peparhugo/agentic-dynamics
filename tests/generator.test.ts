import { execFile } from 'node:child_process';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { buildSite, buildSiteWithStats } from '../src/generator';
import { startDevServer } from '../src/server';

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

  it('renders page templates in layouts with partials and uses the default template', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const contentDir = join(root, 'content');
    const outputDir = join(root, 'public');
    const templatesDir = join(root, 'templates');
    await mkdir(join(templatesDir, 'layouts'), { recursive: true });
    await mkdir(join(templatesDir, 'partials'), { recursive: true });
    await writeFile(join(templatesDir, 'default.hbs'), '<article>{{> header}}<h1>{{title}}</h1>{{{content}}}{{> footer}}</article>');
    await writeFile(join(templatesDir, 'post.hbs'), '<section class="post"><h2>{{title}}</h2>{{{content}}}</section>');
    await writeFile(join(templatesDir, 'layouts', 'default.hbs'), '<!doctype html><body>{{{body}}}</body>');
    await writeFile(join(templatesDir, 'layouts', 'minimal.hbs'), '<main>{{{body}}}</main>');
    await writeFile(join(templatesDir, 'partials', 'header.hbs'), '<header>{{siteName}}</header>');
    await writeFile(join(templatesDir, 'partials', 'footer.hbs'), '<footer>Copyright</footer>');
    await mkdir(contentDir);
    await writeFile(join(contentDir, 'default.md'), '---\ntitle: Default\nsiteName: Example\n---\nHello **world**');
    await writeFile(join(contentDir, 'custom.md'), '---\ntitle: Custom\ntemplate: post\nlayout: minimal\n---\nCustom content');

    await buildSite({ contentDir, outputDir, templatesDir });

    await expect(readFile(join(outputDir, 'default.html'), 'utf8')).resolves.toBe('<!doctype html><body><article><header>Example</header><h1>Default</h1><p>Hello <strong>world</strong></p>\n<footer>Copyright</footer></article></body>');
    await expect(readFile(join(outputDir, 'custom.html'), 'utf8')).resolves.toBe('<main><section class="post"><h2>Custom</h2><p>Custom content</p>\n</section></main>');
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

    expect(stdout).toBe('Generated 1 page(s). Pages built: 1, pages skipped: 0, time saved: 0 page-build(s).\n');
    await expect(readFile(join(outputDir, 'post.html'), 'utf8')).resolves.toContain('<h1>CLI page</h1>');
  });
});

describe('incremental builds', () => {
  it('skips unchanged pages, rebuilds changed sources, and invalidates all pages for template changes', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-incremental-'));
    const contentDir = join(root, 'content');
    const outputDir = join(root, 'public');
    const templatesDir = join(root, 'templates');
    await mkdir(contentDir);
    await mkdir(templatesDir);
    await writeFile(join(templatesDir, 'default.hbs'), '<article>{{title}}: {{{content}}}</article>');
    const first = join(contentDir, 'first.md');
    await writeFile(first, '---\ntitle: First\n---\nOne');
    await writeFile(join(contentDir, 'second.md'), '---\ntitle: Second\n---\nTwo');

    expect((await buildSiteWithStats({ contentDir, outputDir, templatesDir, incremental: true })).stats).toEqual({ pagesBuilt: 2, pagesSkipped: 0, timeSaved: 0 });
    expect((await buildSiteWithStats({ contentDir, outputDir, templatesDir, incremental: true })).stats).toEqual({ pagesBuilt: 0, pagesSkipped: 2, timeSaved: 2 });

    await writeFile(first, '---\ntitle: First\n---\nUpdated');
    expect((await buildSiteWithStats({ contentDir, outputDir, templatesDir, incremental: true })).stats).toEqual({ pagesBuilt: 1, pagesSkipped: 1, timeSaved: 1 });
    await expect(readFile(join(outputDir, 'first.html'), 'utf8')).resolves.toContain('Updated');

    await writeFile(join(templatesDir, 'default.hbs'), '<main>{{title}}: {{{content}}}</main>');
    expect((await buildSiteWithStats({ contentDir, outputDir, templatesDir, incremental: true })).stats).toEqual({ pagesBuilt: 2, pagesSkipped: 0, timeSaved: 0 });
    await expect(readFile(join(outputDir, 'second.html'), 'utf8')).resolves.toContain('<main>Second');

    await rm(join(contentDir, 'second.md'));
    expect((await buildSiteWithStats({ contentDir, outputDir, templatesDir, incremental: true })).stats).toEqual({ pagesBuilt: 0, pagesSkipped: 1, timeSaved: 1 });
    await expect(readFile(join(outputDir, 'second.html'), 'utf8')).rejects.toThrow();
  });

  it('performs a clean build when requested and writes a manifest', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-incremental-clean-'));
    const contentDir = join(root, 'content');
    const outputDir = join(root, 'public');
    await mkdir(contentDir);
    await writeFile(join(contentDir, 'page.md'), '# Page');

    await buildSiteWithStats({ contentDir, outputDir, incremental: true });
    const result = await buildSiteWithStats({ contentDir, outputDir, incremental: true, clean: true });

    expect(result.stats).toEqual({ pagesBuilt: 1, pagesSkipped: 0, timeSaved: 0 });
    await expect(readFile(join(outputDir, '.ssg-cache.json'), 'utf8')).resolves.toContain('page.md');
  });
});

describe('development server', () => {
  it('serves built pages with live reload and rebuilds changed content', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-server-'));
    const contentDir = join(root, 'content');
    const outputDir = join(root, 'public');
    await mkdir(contentDir);
    const pagePath = join(contentDir, 'page.md');
    await writeFile(pagePath, '---\ntitle: First\n---\nInitial');
    const server = await startDevServer({ contentDir, outputDir, templatesDir: resolve('templates'), port: 0 });

    try {
      const page = await fetch(`http://localhost:${server.port}/page.html`);
      expect(page.status).toBe(200);
      await expect(page.text()).resolves.toContain('new WebSocket(`ws://${location.host}`)');

      await writeFile(pagePath, '---\ntitle: Second\n---\nUpdated');
      await new Promise<void>((resolveBuild, reject) => {
        const timeout = setTimeout(() => reject(new Error('Timed out waiting for rebuild')), 5000);
        const interval = setInterval(async () => {
          try {
            const output = await readFile(join(outputDir, 'page.html'), 'utf8');
            if (output.includes('<h1>Second</h1>')) {
              clearTimeout(timeout);
              clearInterval(interval);
              resolveBuild();
            }
          } catch {
            // The output directory is briefly replaced during rebuilds.
          }
        }, 50);
      });
    } finally {
      await server.close();
    }
  });
});
