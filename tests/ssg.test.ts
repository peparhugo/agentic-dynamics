import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { WebSocket } from 'ws';
import { buildSite, parseMarkdown, renderPage, startDevServer } from '../src';
import type { Plugin } from '../src';
import { createProgram } from '../src/cli';

describe('static site generator', () => {
  let workspace: string;

  beforeEach(async () => {
    workspace = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(workspace, { recursive: true, force: true });
  });

  test('parses Markdown and normalizes frontmatter', () => {
    const page = parseMarkdown(`---\ntitle: Hello <World>\ndate: 2024-02-03\ntags: one, two\n---\n# Welcome\n\nThis is **bold**.`, 'hello.md');

    expect(page).toMatchObject({
      title: 'Hello <World>',
      date: '2024-02-03',
      tags: ['one', 'two'],
      outputPath: 'hello.html',
      url: 'hello.html',
    });
    expect(page.html).toContain('<strong>bold</strong>');
    expect(renderPage(page)).toContain('<title>Hello &lt;World&gt;</title>');
  });

  test('uses a readable filename when title is absent', () => {
    expect(parseMarkdown('# Post', 'my-first_post.md').title).toBe('My First Post');
  });

  test('keeps a root index page separate from the generated listing', () => {
    const page = parseMarkdown('# Home', 'index.md');

    expect(page.outputPath).toBe('index-page.html');
    expect(page.url).toBe('index-page.html');
  });

  test('builds nested pages and a date-sorted index', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'public');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'older.md'), '---\ntitle: Older\ndate: 2023-01-01\n---\nOld');
    await fs.writeFile(path.join(content, 'notes', 'new.md'), '---\ntitle: Newer\ndate: 2024-01-01\ntags:\n  - news\n---\nNew');
    await fs.writeFile(path.join(content, 'ignore.txt'), 'not content');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    const nested = await fs.readFile(path.join(output, 'notes', 'new.html'), 'utf8');

    expect(pages.map((page) => page.title)).toEqual(['Newer', 'Older']);
    expect(index).toContain('href="notes/new.html"');
    expect(index.indexOf('Newer')).toBeLessThan(index.indexOf('Older'));
    expect(nested).toContain('<li>news</li>');
    await expect(fs.stat(path.join(output, 'ignore.html'))).rejects.toThrow();
  });

  test('renders pages with the default template, layout, and partials', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'public');
    const templates = path.join(workspace, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello <World>\nsubtitle: A custom value\n---\nMarkdown **content**');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<article><h1>{{title}}</h1><p>{{subtitle}}</p>{{{content}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<!doctype html>{{> header}}<main>{{{body}}}</main>{{> footer}}');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, outputDir: output, templateDir: templates });
    const rendered = await fs.readFile(path.join(output, 'hello.html'), 'utf8');

    expect(rendered).toContain('<header>Hello &lt;World&gt;</header>');
    expect(rendered).toContain('<h1>Hello &lt;World&gt;</h1>');
    expect(rendered).toContain('<p>A custom value</p>');
    expect(rendered).toContain('<p>Markdown <strong>content</strong></p>');
    expect(rendered).toContain('<footer>Footer</footer>');
  });

  test('supports page-selected templates and layouts with optional hbs extensions', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'public');
    const templates = path.join(workspace, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), '---\ntitle: Selected\ntemplate: post.hbs\nlayout: article\n---\nBody');
    await fs.writeFile(path.join(templates, 'post.hbs'), '<section>{{{content}}}</section>');
    await fs.writeFile(path.join(templates, 'layouts', 'article.hbs'), '<html><title>{{title}}</title>{{{body}}}</html>');

    const [page] = await buildSite({ contentDir: content, outputDir: output, templateDir: templates });

    expect(page.template).toBe('post.hbs');
    expect(page.layout).toBe('article');
    await expect(fs.readFile(path.join(output, 'post.html'), 'utf8')).resolves.toBe(
      '<html><title>Selected</title><section><p>Body</p>\n</section></html>',
    );
  });

  test('reports a missing selected template', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'public');
    const templates = path.join(workspace, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), '---\ntemplate: missing\n---\nBody');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '{{{body}}}');

    await expect(buildSite({ contentDir: content, outputDir: output, templateDir: templates }))
      .rejects.toThrow('Template not found: missing');
  });

  test('cleans stale output and supports an empty content directory', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'output');
    await fs.mkdir(content);
    await fs.mkdir(output);
    await fs.writeFile(path.join(output, 'stale.html'), 'stale');

    await expect(buildSite({ contentDir: content, outputDir: output })).resolves.toEqual([]);
    await expect(fs.stat(path.join(output, 'stale.html'))).rejects.toThrow();
    await expect(fs.readFile(path.join(output, 'index.html'), 'utf8')).resolves.toContain('No pages found.');
  });

  test('reports a missing content directory', async () => {
    await expect(buildSite({
      contentDir: path.join(workspace, 'missing'),
      outputDir: path.join(workspace, 'output'),
    })).rejects.toThrow('Content directory does not exist');
  });

  test('refuses overlapping content and output directories', async () => {
    const content = path.join(workspace, 'content');
    await fs.mkdir(content);

    await expect(buildSite({
      contentDir: content,
      outputDir: path.join(content, 'dist'),
    })).rejects.toThrow('Content and output directories must not overlap');
    await expect(buildSite({
      contentDir: content,
      outputDir: workspace,
    })).rejects.toThrow('Content and output directories must not overlap');
  });

  test('runs plugin hooks in order and renders onFile replacements', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# Original');
    const calls: string[] = [];
    const plugin = (name: string): Plugin => ({
      onStart: () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: (page) => {
        calls.push(`${name}:file`);
        return name === 'second' ? { ...page, title: 'Changed' } : undefined;
      },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); },
    });

    const pages = await buildSite({ contentDir: content, outputDir: output, plugins: [plugin('first'), plugin('second')] });

    expect(calls).toEqual([
      'first:start', 'second:start', 'first:before', 'second:before',
      'first:file', 'second:file', 'first:after', 'second:after', 'first:end', 'second:end',
    ]);
    expect(pages[0].title).toBe('Changed');
    await expect(fs.readFile(path.join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>Changed</h1>');
  });

  test('loads plugins from a TypeScript config file', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'output');
    const config = path.join(workspace, 'ssg.config.ts');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# Original');
    await fs.writeFile(config, `export default {
      plugins: [{ onFile(page: any) { return { ...page, title: 'Configured' }; } }]
    };`);

    const pages = await buildSite({ contentDir: content, outputDir: output, configFile: config });

    expect(pages[0].title).toBe('Configured');
    await expect(fs.readFile(path.join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>Configured</h1>');
  });

  test('runs onEnd when a build hook fails', async () => {
    const content = path.join(workspace, 'content');
    await fs.mkdir(content);
    let ended = false;

    await expect(buildSite({
      contentDir: content,
      outputDir: path.join(workspace, 'output'),
      plugins: [{ beforeBuild: () => { throw new Error('broken'); }, onEnd: () => { ended = true; } }],
    })).rejects.toThrow('broken');
    expect(ended).toBe(true);
  });

  test('CLI build honors content and output options', async () => {
    const content = path.join(workspace, 'articles');
    const output = path.join(workspace, 'site');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# CLI page');
    const write = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    await createProgram().parseAsync(['node', 'ssg', 'build', '--content', content, '--output', output]);

    await expect(fs.readFile(path.join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>CLI page</h1>');
    expect(write).toHaveBeenCalledWith(`Generated 1 page in ${output}\n`);
    write.mockRestore();
  });

  test('serves dist with live reload and rebuilds changed content', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'dist');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# Before');
    const server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });

    const request = (pathname: string): Promise<string> => new Promise((resolve, reject) => {
      http.get({ hostname: server.host, port: server.port, path: pathname }, (response) => {
        const chunks: Buffer[] = [];
        response.on('data', (chunk: Buffer) => chunks.push(chunk));
        response.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      }).on('error', reject);
    });

    try {
      const initial = await request('/page.html');
      expect(initial).toContain('<h1>Before</h1>');
      expect(initial).toContain("new WebSocket");

      const socket = new WebSocket(`ws://${server.host}:${server.port}/__ssg_reload`);
      await new Promise<void>((resolve, reject) => {
        socket.once('open', resolve);
        socket.once('error', reject);
      });
      const reloaded = new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
        socket.once('message', (message) => {
          clearTimeout(timeout);
          expect(message.toString()).toBe('reload');
          resolve();
        });
      });

      await fs.writeFile(path.join(content, 'page.md'), '# After');
      await reloaded;
      await expect(request('/page.html')).resolves.toContain('<h1>After</h1>');
      socket.close();
    } finally {
      await server.close();
    }
  });
});
