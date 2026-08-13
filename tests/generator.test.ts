import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type Plugin } from '../src';

describe('buildSite', () => {
  let temporaryDirectory: string;

  beforeEach(async () => {
    temporaryDirectory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(temporaryDirectory, { recursive: true, force: true });
  });

  it('renders Markdown and frontmatter into pages and an index', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello <World>
date: 2025-02-03
tags:
  - news
  - typescript
---
# Welcome

This is **static**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toEqual([expect.objectContaining({
      title: 'Hello <World>',
      date: '2025-02-03',
      tags: ['news', 'typescript'],
      url: 'hello.html',
    })]);
    expect(page).toContain('<title>Hello &lt;World&gt;</title>');
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>static</strong>');
    expect(page).toContain('<li>typescript</li>');
    expect(index).toContain('<a href="hello.html">Hello &lt;World&gt;</a>');
  });

  it('preserves nested paths and falls back to the filename for a title', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(path.join(contentDir, 'notes'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'notes', 'first.md'), 'A paragraph.');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages[0]).toEqual(expect.objectContaining({ title: 'first', url: 'notes/first.html' }));
    await expect(fs.readFile(path.join(outputDir, 'notes', 'first.html'), 'utf8'))
      .resolves.toContain('<p>A paragraph.</p>');
  });

  it('creates an empty index and removes stale output', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(contentDir);
    await fs.mkdir(outputDir);
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'stale');

    await expect(buildSite({ contentDir, outputDir })).resolves.toEqual([]);
    await expect(fs.stat(path.join(outputDir, 'stale.html'))).rejects.toThrow();
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('<h1>Pages</h1>');
  });

  it('uses the default template, layout, and partials', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    const templatesDir = path.join(temporaryDirectory, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'partials'));
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello
layout: base
author: Sam & Pat
---
This is **templated**.`);
    await fs.writeFile(
      path.join(templatesDir, 'default.hbs'),
      '<article>{{> header}}<p>{{author}}</p>{{{content}}}</article>',
    );
    await fs.writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<h1>{{title}}</h1>');
    await fs.writeFile(
      path.join(templatesDir, 'layouts', 'base.hbs'),
      '<!doctype html><html><body>{{{body}}}{{> footer}}</body></html>',
    );
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>{{title}}</footer>');

    await buildSite({ contentDir, outputDir, templatesDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(page).toBe('<!doctype html><html><body><article><h1>Hello</h1><p>Sam &amp; Pat</p><p>This is <strong>templated</strong>.</p>\n</article><footer>Hello</footer></body></html>');
  });

  it('allows each page to select a template', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    const templatesDir = path.join(temporaryDirectory, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), `---
title: Selected
template: post.hbs
---
# Body`);
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), 'default {{{content}}}');
    await fs.writeFile(path.join(templatesDir, 'post.hbs'), '<main data-title="{{title}}">{{{content}}}</main>');

    await buildSite({ contentDir, outputDir, templatesDir });

    await expect(fs.readFile(path.join(outputDir, 'post.html'), 'utf8'))
      .resolves.toBe('<main data-title="Selected"><h1>Body</h1>\n</main>');
  });

  it('reports a missing selected template', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    const templatesDir = path.join(temporaryDirectory, 'templates');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), '---\ntemplate: missing\n---\nBody');

    await expect(buildSite({ contentDir, outputDir, templatesDir }))
      .rejects.toThrow('Template not found: missing');
  });

  it('runs plugin lifecycle hooks in order and lets plugins transform pages', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), '# Original');
    const calls: string[] = [];
    const first: Plugin = {
      onStart: () => { calls.push('first:start'); },
      beforeBuild: () => { calls.push('first:before'); },
      onFile: (page) => {
        calls.push(`first:file:${page.title}`);
        page.html = '<p>Changed</p>';
      },
      afterBuild: () => { calls.push('first:after'); },
      onEnd: () => { calls.push('first:end'); },
    };
    const second: Plugin = {
      onStart: () => { calls.push('second:start'); },
      beforeBuild: () => { calls.push('second:before'); },
      onFile: (page) => { calls.push(`second:file:${page.title}`); },
      afterBuild: () => { calls.push('second:after'); },
      onEnd: () => { calls.push('second:end'); },
    };

    await buildSite({ contentDir, outputDir, plugins: [first, second] });

    await expect(fs.readFile(path.join(outputDir, 'post.html'), 'utf8')).resolves.toContain('<p>Changed</p>');
    expect(calls).toEqual([
      'first:start', 'second:start',
      'first:before', 'second:before',
      'first:file:post', 'second:file:post',
      'first:after', 'second:after',
      'first:end', 'second:end',
    ]);
  });

  it('loads TypeScript plugins from the configured ssg config', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    const pluginsDir = path.join(temporaryDirectory, 'plugins');
    const configFile = path.join(temporaryDirectory, 'ssg.config.ts');
    await fs.mkdir(contentDir);
    await fs.mkdir(pluginsDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), '# Original');
    await fs.writeFile(path.join(pluginsDir, 'suffix.ts'), `
      export default {
        onFile(page: { html: string }): void {
          page.html += '<p>From config</p>';
        },
      };
    `);
    await fs.writeFile(configFile, `
      import suffix from './plugins/suffix';
      export default { plugins: [suffix] };
    `);

    await buildSite({ contentDir, outputDir, configFile });

    await expect(fs.readFile(path.join(outputDir, 'post.html'), 'utf8'))
      .resolves.toContain('<p>From config</p>');
  });
});
