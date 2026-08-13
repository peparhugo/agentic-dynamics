import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('renders frontmatter, Markdown, and an index', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'public');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'hello.md'), `---
title: Hello World
date: 2024-01-02
tags: [news, welcome]
---
This is **important**.
`);

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');

    expect(pages).toEqual([expect.objectContaining({
      title: 'Hello World',
      date: '2024-01-02',
      tags: ['news', 'welcome'],
      url: 'hello.html',
    })]);
    expect(page).toContain('<strong>important</strong>');
    expect(page).toContain('<title>Hello World</title>');
    expect(page).toContain('Tags: news, welcome');
    expect(index).toContain('<a href="hello.html">Hello World</a>');
  });

  test('supports nested pages, title fallback, and cleans stale output', async () => {
    const content = path.join(root, 'articles');
    const output = path.join(root, 'site');
    await fs.mkdir(path.join(content, 'guides'), { recursive: true });
    await fs.mkdir(output);
    await fs.writeFile(path.join(content, 'guides', 'start.md'), '# Start');
    await fs.writeFile(path.join(content, 'ignore.txt'), 'not a page');
    await fs.writeFile(path.join(output, 'stale.html'), 'old');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages).toHaveLength(1);
    expect(pages[0]).toEqual(expect.objectContaining({ title: 'start', url: 'guides/start.html' }));
    await expect(fs.readFile(path.join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<h1>Start</h1>');
    await expect(fs.stat(path.join(output, 'stale.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test('escapes frontmatter inserted into HTML', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'safe.md'), '---\ntitle: "<script>alert(1)</script>"\n---\nText');

    await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'safe.html'), 'utf8');

    expect(page).not.toContain('<script>');
    expect(page).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  test('renders an explicit template, layout, and partials', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.writeFile(path.join(content, 'post.md'), `---
title: Template Post
template: article
layout: main
author: Ada
---
Hello **templates**.
`);
    await fs.writeFile(path.join(templates, 'article.hbs'), '<article>{{> header}}<p>{{author}}</p>{{{content}}}</article>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templates, 'layouts', 'main.hbs'), '<!doctype html><nav>{{> nav}}</nav><main>{{{body}}}</main>');
    await fs.writeFile(path.join(templates, 'partials', 'nav.hbs'), '<a href="/">Home</a>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });
    const page = await fs.readFile(path.join(output, 'post.html'), 'utf8');

    expect(page).toBe('<!doctype html><nav><a href="/">Home</a></nav><main><article><header>Template Post</header><p>Ada</p><p>Hello <strong>templates</strong>.</p></article></main>');
  });

  test('uses default templates and layouts and supports layout opt-out', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(content, 'wrapped.md'), '---\ntitle: Wrapped\n---\nDefault');
    await fs.writeFile(path.join(content, 'plain.md'), '---\ntitle: Plain\nlayout: false\n---\nNo layout');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<section data-url="{{url}}"><h1>{{title}}</h1>{{{content}}}</section>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    await expect(fs.readFile(path.join(output, 'wrapped.html'), 'utf8'))
      .resolves.toBe('<html><body><section data-url="wrapped.html"><h1>Wrapped</h1><p>Default</p></section></body></html>');
    await expect(fs.readFile(path.join(output, 'plain.html'), 'utf8'))
      .resolves.toBe('<section data-url="plain.html"><h1>Plain</h1><p>No layout</p></section>');
  });

  test('reports missing templates and rejects template path traversal', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'post.md'), '---\ntemplate: missing\n---\nPost');
    await expect(buildSite({ contentDir: content, outputDir: output, templatesDir: templates }))
      .rejects.toThrow('Template not found: missing');

    await fs.writeFile(path.join(content, 'post.md'), '---\ntemplate: ../outside\n---\nPost');
    await expect(buildSite({ contentDir: content, outputDir: output, templatesDir: templates }))
      .rejects.toThrow('Invalid template path: ../outside');
  });

  test('rejects paths that could overwrite content or the generated index', async () => {
    const content = path.join(root, 'site', 'content');
    await fs.mkdir(content, { recursive: true });
    await fs.writeFile(path.join(content, 'post.md'), 'Post');

    await expect(buildSite({ contentDir: content, outputDir: path.dirname(content) }))
      .rejects.toThrow('must not overlap');

    const separateOutput = path.join(root, 'output');
    await fs.writeFile(path.join(content, 'index.md'), 'Index content');
    await expect(buildSite({ contentDir: content, outputDir: separateOutput }))
      .rejects.toThrow('index.md conflicts');
  });
});
