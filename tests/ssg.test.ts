import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { runCli } from '../src/cli';
import { buildSite, Plugin } from '../src';
import { startDevServer } from '../src/server';

describe('static site generator', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'public');
    templatesDir = path.join(root, 'templates');
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

  test('runs plugin lifecycle hooks in order for each page', async () => {
    await fs.writeFile(path.join(contentDir, 'b.md'), '# B');
    await fs.writeFile(path.join(contentDir, 'a.md'), '# A');
    const calls: string[] = [];
    const plugin = (name: string): Plugin => ({
      onStart: () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: page => {
        calls.push(`${name}:file:${page.title}`);
        page.html = page.html.replace('</h1>', ` ${name}</h1>`);
      },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); }
    });

    await buildSite({ contentDir, outputDir, plugins: [plugin('one'), plugin('two')] });

    expect(calls).toEqual([
      'one:start', 'two:start',
      'one:before', 'two:before',
      'one:file:A', 'two:file:A',
      'one:file:B', 'two:file:B',
      'one:after', 'two:after',
      'one:end', 'two:end'
    ]);
    await expect(fs.readFile(path.join(outputDir, 'a.html'), 'utf8'))
      .resolves.toContain('<h1>A one two</h1>');
  });

  test('loads ordered plugins from ssg.config.ts', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Original');
    const configFile = path.join(root, 'ssg.config.ts');
    await fs.writeFile(configFile, `
      export default {
        plugins: [{
          onFile(page: { title: string }) {
            page.title = 'Configured';
          }
        }]
      };
    `);

    const pages = await buildSite({ contentDir, outputDir, configFile });

    expect(pages[0].title).toBe('Configured');
    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8'))
      .resolves.toContain('<title>Configured</title>');
  });

  test('runs onEnd after a failed build', async () => {
    const onEnd = jest.fn();
    const plugin: Plugin = {
      beforeBuild: () => { throw new Error('plugin failed'); },
      onEnd
    };

    await expect(buildSite({ contentDir, outputDir, plugins: [plugin] }))
      .rejects.toThrow('plugin failed');
    expect(onEnd).toHaveBeenCalledTimes(1);
  });

  test('uses a default Handlebars template and default layout', async () => {
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'),
      '<article data-kind="{{kind}}"><h1>{{title}}</h1>{{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!doctype html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>');
    await fs.writeFile(path.join(contentDir, 'welcome.md'),
      '---\ntitle: Welcome\nkind: guide\n---\nText with **markup**.');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'welcome.html'), 'utf8');

    expect(html).toContain('<title>Welcome</title>');
    expect(html).toContain('<article data-kind="guide">');
    expect(html).toContain('<p>Text with <strong>markup</strong>.</p>');
  });

  test('selects page templates and layouts from frontmatter', async () => {
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<p>default</p>');
    await fs.writeFile(path.join(templatesDir, 'post.hbs'), '<article>{{title}}: {{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'site.hbs'), '<main class="site">{{{body}}}</main>');
    await fs.writeFile(path.join(contentDir, 'post.md'),
      '---\ntitle: Selected\ntemplate: post.hbs\nlayout: site.hbs\n---\nBody');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'post.html'), 'utf8');

    expect(html).toBe('<main class="site"><article>Selected: <p>Body</p>\n</article></main>');
  });

  test('supports a layout without requiring a page template', async () => {
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!doctype html><body class="layout">{{{body}}}</body>');
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Layout only\n---\nBody');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'page.html'), 'utf8');

    expect(html).toContain('<body class="layout"><main>');
    expect(html).not.toContain('<body class="layout"><!doctype html>');
  });

  test('registers reusable Handlebars partials', async () => {
    await fs.mkdir(path.join(templatesDir, 'partials'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'),
      '{{> header}}<main>{{{content}}}</main>{{> footer}}');
    await fs.writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>End</footer>');
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Partials\n---\nPage');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'page.html'), 'utf8');

    expect(html).toBe('<header>Partials</header><main><p>Page</p>\n</main><footer>End</footer>');
  });

  test('fails clearly when a selected template does not exist', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntemplate: missing\n---\nPage');

    await expect(buildSite({ contentDir, outputDir, templatesDir }))
      .rejects.toThrow('Template not found: missing.hbs');
  });

  test('fails clearly when a selected layout does not exist', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\nlayout: missing\n---\nPage');

    await expect(buildSite({ contentDir, outputDir, templatesDir }))
      .rejects.toThrow('Layout not found: missing.hbs');
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

  test('incremental builds skip unchanged pages and persist their output', async () => {
    const cacheFile = path.join(root, '.ssg-cache.json');
    await fs.writeFile(path.join(contentDir, 'one.md'), '# One');
    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two');

    const first = await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });
    const firstStat = await fs.stat(path.join(outputDir, 'one.html'));
    await new Promise(resolve => setTimeout(resolve, 20));
    const second = await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });
    const secondStat = await fs.stat(path.join(outputDir, 'one.html'));

    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(second.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });
    expect(second.stats.timeSavedMs).toBeGreaterThan(0);
    expect(secondStat.mtimeMs).toBe(firstStat.mtimeMs);
    const manifest = JSON.parse(await fs.readFile(cacheFile, 'utf8')) as { pages: Record<string, unknown> };
    expect(Object.keys(manifest.pages)).toEqual(['one.md', 'two.md']);
  });

  test('incremental builds rebuild only a changed source', async () => {
    const cacheFile = path.join(root, '.ssg-cache.json');
    const unchanged = path.join(outputDir, 'one.html');
    const changed = path.join(outputDir, 'two.html');
    await fs.writeFile(path.join(contentDir, 'one.md'), '# One');
    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two');
    await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });
    const before = await Promise.all([fs.stat(unchanged), fs.stat(changed)]);
    await new Promise(resolve => setTimeout(resolve, 20));

    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two changed');
    const result = await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });
    const after = await Promise.all([fs.stat(unchanged), fs.stat(changed)]);

    expect(result.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(after[0].mtimeMs).toBe(before[0].mtimeMs);
    expect(after[1].mtimeMs).toBeGreaterThan(before[1].mtimeMs);
    await expect(fs.readFile(changed, 'utf8')).resolves.toContain('Two changed');
  });

  test('template changes invalidate all incremental pages', async () => {
    const cacheFile = path.join(root, '.ssg-cache.json');
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<main>{{title}}</main>');
    await fs.writeFile(path.join(contentDir, 'one.md'), '# One');
    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two');
    await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });

    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{title}}</article>');
    const result = await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });

    expect(result.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8'))
      .resolves.toBe('<article>One</article>');
  });

  test('clean incremental builds ignore existing cache and remove stale output', async () => {
    const cacheFile = path.join(root, '.ssg-cache.json');
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'stale');

    const result = await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true, clean: true });

    expect(result.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    await expect(fs.stat(path.join(outputDir, 'stale.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test('incremental builds remove output for deleted sources', async () => {
    const cacheFile = path.join(root, '.ssg-cache.json');
    const source = path.join(contentDir, 'page.md');
    const output = path.join(outputDir, 'page.html');
    await fs.writeFile(source, '# Page');
    await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });

    await fs.rm(source);
    const result = await buildSite({ contentDir, outputDir, templatesDir, cacheFile, incremental: true });

    expect(result).toHaveLength(0);
    await expect(fs.stat(output)).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test('CLI accepts incremental builds and reports build stats', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    const exitCode = await runCli(
      ['build', '--content', contentDir, '--output', outputDir, '--templates', templatesDir,
        '--incremental', '--cache', path.join(root, '.ssg-cache.json')],
      { stdout, stderr }
    );

    expect(exitCode).toBe(0);
    expect(stdout.write).toHaveBeenLastCalledWith(expect.stringMatching(/^Build stats: 1 built, 0 skipped, .*ms saved\.\n$/));
    expect(stderr.write).not.toHaveBeenCalled();
  });

  test('runs build with a custom CLI templates directory', async () => {
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<section>{{title}}</section>');
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    const exitCode = await runCli(
      ['build', '--content', contentDir, '--output', outputDir, '--templates', templatesDir],
      { stdout, stderr }
    );

    expect(exitCode).toBe(0);
    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8'))
      .resolves.toBe('<section>Page</section>');
  });

  test('rejects invalid CLI input', async () => {
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    await expect(runCli([], { stdout, stderr })).resolves.toBe(1);
    await expect(runCli(['build', '--other'], { stdout, stderr })).resolves.toBe(1);
    expect(stderr.write).toHaveBeenCalledTimes(2);
  });

  test('rejects an invalid serve port', async () => {
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    await expect(runCli(['serve', '--port', '70000'], { stdout, stderr })).resolves.toBe(1);
    expect(stderr.write).toHaveBeenCalledWith('Invalid port: 70000\n');
  });

  test('serves generated pages with the live reload client', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Original');
    const server = await startDevServer({
      contentDir,
      outputDir,
      templatesDir,
      host: '127.0.0.1',
      port: 0
    });

    try {
      const response = await fetch(`http://127.0.0.1:${server.port}/page.html`);
      const html = await response.text();

      expect(response.status).toBe(200);
      expect(response.headers.get('cache-control')).toBe('no-store');
      expect(html).toContain('<h1>Original</h1>');
      expect(html).toContain('/__ssg_reload');
      expect(html.indexOf('/__ssg_reload')).toBeLessThan(html.indexOf('</body>'));
    } finally {
      await server.close();
    }
  });

  test('rebuilds and broadcasts reload when content changes', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Before');
    const server = await startDevServer({
      contentDir,
      outputDir,
      templatesDir,
      host: '127.0.0.1',
      port: 0
    });
    const socket = new WebSocket(`ws://127.0.0.1:${server.port}/__ssg_reload`);

    try {
      await new Promise<void>((resolve, reject) => {
        socket.once('open', resolve);
        socket.once('error', reject);
      });
      const reload = new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
        socket.once('message', message => {
          clearTimeout(timeout);
          expect(message.toString()).toBe('reload');
          resolve();
        });
      });

      await fs.writeFile(path.join(contentDir, 'page.md'), '# After');
      await reload;
      await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8'))
        .resolves.toContain('<h1>After</h1>');
    } finally {
      socket.terminate();
      await server.close();
    }
  });
});
