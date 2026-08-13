import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, createEngine, type Plugin } from '../src';

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

  it('renders the default template, layout, and partials', async () => {
    const templates = path.join(root, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.writeFile(path.join(templates, 'default.hbs'), `{{> header}}
<article data-kind="{{kind}}">{{{content}}}</article>
{{> footer}}`);
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<html><body>{{> nav}}{{{body}}}</body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');
    await fs.writeFile(path.join(templates, 'partials', 'nav.hbs'), '<nav>Navigation</nav>');
    await fs.writeFile(path.join(content, 'post.md'), `---
title: '<Default>'
kind: guide
---
Hello **templates**.
`);

    await buildSite({ content, output, templates });
    const generated = await fs.readFile(path.join(output, 'post.html'), 'utf8');

    expect(generated).toBe(`<html><body><nav>Navigation</nav><header>&lt;Default&gt;</header>
<article data-kind="guide"><p>Hello <strong>templates</strong>.</p>
</article>
<footer>Footer</footer></body></html>`);
  });

  it('supports per-page templates and layouts', async () => {
    const templates = path.join(root, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templates, 'article.hbs'), '<section><h1>{{title}}</h1>{{{content}}}</section>');
    await fs.writeFile(path.join(templates, 'layouts', 'wide.hbs'), '<div class="wide">{{{body}}}</div>');
    await fs.writeFile(path.join(content, 'post.md'), `---
title: Custom page
template: article
layout: wide.hbs
---
Page body.
`);

    await buildSite({ content, output, templates });

    expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toBe(
      '<div class="wide"><section><h1>Custom page</h1><p>Page body.</p>\n</section></div>',
    );
  });

  it('reports missing named templates and unknown partials', async () => {
    const templates = path.join(root, 'templates');
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'missing.md'), '---\ntemplate: absent\n---\nBody');

    await expect(buildSite({ content, output, templates })).rejects.toThrow('Template not found: absent');

    await fs.writeFile(path.join(templates, 'absent.hbs'), '{{> unknown}}');
    await expect(buildSite({ content, output, templates })).rejects.toThrow('partial unknown');
  });

  it('runs plugin lifecycle hooks in order and allows page transforms', async () => {
    await fs.writeFile(path.join(content, 'post.md'), '# Body');
    const calls: string[] = [];
    const plugin = (name: string): Plugin => ({
      name,
      onStart: () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: (page) => { calls.push(`${name}:file`); page.title += name; },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); },
    });

    const engine = await createEngine({ content, output, config: false, plugins: [plugin('A'), plugin('B')] });
    await engine.start();
    const pages = await engine.build();
    await engine.end();

    expect(pages[0].title).toBe('postAB');
    expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toContain('<title>postAB</title>');
    expect(calls).toEqual([
      'A:start', 'B:start', 'A:before', 'B:before', 'A:file', 'B:file',
      'A:after', 'B:after', 'A:end', 'B:end',
    ]);
  });

  it('loads TypeScript plugins from ssg.config.ts', async () => {
    const plugins = path.join(root, 'plugins');
    await fs.mkdir(plugins);
    await fs.writeFile(path.join(content, 'post.md'), 'Body');
    await fs.writeFile(path.join(plugins, 'title.ts'), `
      import type { Plugin } from '${path.resolve(__dirname, '../src').replaceAll('\\', '\\\\')}';
      const plugin: Plugin = { onFile(page) { page.title = 'Configured'; } };
      export default plugin;
    `);
    await fs.writeFile(path.join(root, 'ssg.config.ts'), `
      import title from './plugins/title';
      export default { plugins: [title] };
    `);

    const pages = await buildSite({ content, output, config: path.join(root, 'ssg.config.ts') });

    expect(pages[0].title).toBe('Configured');
    expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toContain('<title>Configured</title>');
  });

  it('skips unchanged pages during incremental builds', async () => {
    await fs.writeFile(path.join(content, 'one.md'), 'First');
    await fs.writeFile(path.join(content, 'two.md'), 'Second');

    const first = await createEngine({ content, output, incremental: true, config: false });
    await first.build();
    await first.end();
    expect(first.stats.pagesBuilt).toBe(2);
    expect(first.stats.pagesSkipped).toBe(0);

    const oneOutput = path.join(output, 'one.html');
    const twoOutput = path.join(output, 'two.html');
    const oneTime = (await fs.stat(oneOutput)).mtimeMs;
    const twoTime = (await fs.stat(twoOutput)).mtimeMs;
    await new Promise((resolve) => setTimeout(resolve, 20));

    const second = await createEngine({ content, output, incremental: true, config: false });
    const pages = await second.build();
    await second.end();

    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    expect(pages.map((page) => page.title)).toEqual(['one', 'two']);
    expect((await fs.stat(oneOutput)).mtimeMs).toBe(oneTime);
    expect((await fs.stat(twoOutput)).mtimeMs).toBe(twoTime);
    expect(JSON.parse(await fs.readFile(path.join(output, '.ssg-cache.json'), 'utf8'))).toMatchObject({
      version: 1,
      pages: { 'one.md': { sourceHash: expect.any(String) }, 'two.md': { sourceHash: expect.any(String) } },
    });
  });

  it('rebuilds only a changed source and removes deleted page output', async () => {
    const oneSource = path.join(content, 'one.md');
    const twoSource = path.join(content, 'two.md');
    await fs.writeFile(oneSource, 'First');
    await fs.writeFile(twoSource, 'Second');
    await buildSite({ content, output, incremental: true, config: false });
    const twoOutput = path.join(output, 'two.html');
    const twoTime = (await fs.stat(twoOutput)).mtimeMs;
    await new Promise((resolve) => setTimeout(resolve, 20));

    await fs.writeFile(oneSource, 'First changed');
    const changed = await createEngine({ content, output, incremental: true, config: false });
    await changed.build();
    await changed.end();
    expect(changed.stats.pagesBuilt).toBe(1);
    expect(changed.stats.pagesSkipped).toBe(1);
    expect(await fs.readFile(path.join(output, 'one.html'), 'utf8')).toContain('First changed');
    expect((await fs.stat(twoOutput)).mtimeMs).toBe(twoTime);

    await fs.rm(twoSource);
    await buildSite({ content, output, incremental: true, config: false });
    await expect(fs.stat(twoOutput)).rejects.toThrow();
  });

  it('invalidates all pages when templates change and supports clean builds', async () => {
    const templates = path.join(root, 'templates');
    await fs.mkdir(templates);
    await fs.writeFile(path.join(templates, 'default.hbs'), '<article>{{{content}}}</article>');
    await fs.writeFile(path.join(content, 'post.md'), 'Body');
    await buildSite({ content, output, templates, incremental: true, config: false });

    await fs.writeFile(path.join(templates, 'default.hbs'), '<main>{{{content}}}</main>');
    const changed = await createEngine({ content, output, templates, incremental: true, config: false });
    await changed.build();
    await changed.end();
    expect(changed.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toContain('<main>');

    const clean = await createEngine({ content, output, templates, incremental: true, clean: true, config: false });
    await clean.build();
    await clean.end();
    expect(clean.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
  });
});
