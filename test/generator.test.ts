import { mkdtemp, mkdir, readFile, stat, unlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, buildSiteWithStats } from '../src/generator';
import { parseArguments } from '../src/cli';
import { startDevServer } from '../src/server';
import { loadConfiguredPlugins } from '../src/config';
import { Plugin } from '../src/plugin';

describe('buildSite', () => {
  it('runs plugin lifecycle hooks in order', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const calls: string[] = [];
    const plugin = (name: string): Plugin => ({
      onStart: () => calls.push(`${name}:start`),
      beforeBuild: () => calls.push(`${name}:before`),
      onFile: (page) => calls.push(`${name}:file:${page.outputPath}`),
      afterBuild: () => calls.push(`${name}:after`),
      onEnd: () => calls.push(`${name}:end`),
    });
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page');

    await buildSite({ contentDir: content, outputDir: join(root, 'output'), plugins: [plugin('first'), plugin('second')] });

    expect(calls).toEqual([
      'first:start', 'second:start',
      'first:before', 'second:before',
      'first:file:page.html', 'second:file:page.html',
      'first:after', 'second:after',
      'first:end', 'second:end',
    ]);
  });

  it('renders frontmatter, Markdown pages, and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'hello.md'), '---\ntitle: Hello World\ndate: 2026-08-13\ntags:\n  - intro\n  - welcome\n---\n\n# Welcome\n\nA **site** page.');
    await writeFile(join(content, 'guides', 'start.markdown'), '# Getting Started');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages.map((page) => page.outputPath)).toEqual(['guides/start.html', 'hello.html']);
    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toContain('<h1>Welcome</h1>');
    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toContain('Tags: intro, welcome');
    await expect(readFile(join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<title>start</title>');
    await expect(readFile(join(output, 'index.html'), 'utf8')).resolves.toContain('href="guides/start.html"');
  });

  it('renders Handlebars templates, layouts, and partials', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'), { recursive: true });
    await writeFile(join(content, 'post.md'), '---\ntitle: Template Page\ntemplate: post\nlayout: site\nauthor: Ada\n---\n\n# Body');
    await writeFile(join(templates, 'post.hbs'), '<article><h1>{{title}}</h1><p>{{author}}</p>{{{content}}}</article>');
    await writeFile(join(templates, 'layouts', 'site.hbs'), '<!doctype html><html><body>{{> header}} {{{body}}} {{> footer}}</body></html>');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });

    await expect(readFile(join(output, 'post.html'), 'utf8')).resolves.toBe('<!doctype html><html><body><header>Header</header> <article><h1>Template Page</h1><p>Ada</p><h1>Body</h1></article> <footer>Footer</footer></body></html>');
  });

  it('uses the default template and layout when no frontmatter selection is supplied', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await writeFile(join(content, 'page.md'), '---\ntitle: Default Page\n---\n\nText');
    await writeFile(join(templates, 'default.hbs'), '<main>{{title}}: {{{content}}}</main>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });

    await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toBe('<html><main>Default Page: <p>Text</p></main></html>');
  });

  it('skips unchanged pages during incremental builds', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'first.md'), '# First');
    await writeFile(join(content, 'second.md'), '# Second');

    await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true });
    const firstOutput = join(output, 'first.html');
    const initialMtime = (await stat(firstOutput)).mtimeMs;
    const result = await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true });

    expect(result.stats).toMatchObject({ built: 0, skipped: 2 });
    expect((await stat(firstOutput)).mtimeMs).toBe(initialMtime);
    await expect(readFile(join(output, '.ssg-cache.json'), 'utf8')).resolves.toContain('first.html');
  });

  it('rebuilds only changed source pages and invalidates all pages for template changes', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await mkdir(templates, { recursive: true });
    await writeFile(join(content, 'first.md'), '---\ntemplate: default\n---\n# First');
    await writeFile(join(content, 'second.md'), '---\ntemplate: default\n---\n# Second');
    await writeFile(join(templates, 'default.hbs'), '<article>{{{content}}}</article>');

    await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    await writeFile(join(content, 'first.md'), '---\ntemplate: default\n---\n# Updated');
    const sourceResult = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(sourceResult.stats).toMatchObject({ built: 1, skipped: 1 });
    await expect(readFile(join(output, 'first.html'), 'utf8')).resolves.toContain('Updated');

    await writeFile(join(templates, 'default.hbs'), '<main>{{{content}}}</main>');
    const templateResult = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(templateResult.stats).toMatchObject({ built: 2, skipped: 0 });
    await expect(readFile(join(output, 'second.html'), 'utf8')).resolves.toContain('<main>');
  });

  it('performs a clean build when requested', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page');

    await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true });
    const result = await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true, clean: true });

    expect(result.stats).toMatchObject({ built: 1, skipped: 0 });
  });

  it('removes output for deleted pages during incremental builds', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'deleted.md'), '# Deleted');
    await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true });

    await writeFile(join(content, 'replacement.md'), '# Replacement');
    await unlink(join(content, 'deleted.md'));
    await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true });

    await expect(readFile(join(output, 'deleted.html'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
  });
});

describe('loadConfiguredPlugins', () => {
  it('loads plugins from a TypeScript config module', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const config = join(root, 'ssg.config.ts');
    await writeFile(config, 'export default { plugins: [{ onStart() {} }] };');

    expect(loadConfiguredPlugins(config)).toHaveLength(1);
  });
});

describe('parseArguments', () => {
  it('accepts custom content and output directories', () => {
    expect(parseArguments(['--content', 'posts', '--output', 'public', '--templates', 'views'])).toEqual({ contentDir: 'posts', outputDir: 'public', templatesDir: 'views' });
  });

  it('accepts incremental build flags', () => {
    expect(parseArguments(['--incremental', '--clean'])).toEqual({ incremental: true, clean: true });
  });

  it('rejects invalid options', () => {
    expect(() => parseArguments(['--nope'])).toThrow('Unknown option: --nope');
  });

  it('accepts a port for the serve command', () => {
    expect(parseArguments(['--port', '4000'], true)).toEqual({ port: 4000 });
    expect(() => parseArguments(['--port', 'invalid'], true)).toThrow('--port requires a number');
  });
});

describe('startDevServer', () => {
  it('serves generated pages with the live reload client', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page');
    const server = await startDevServer({ contentDir: content, outputDir: output, templatesDir: join(root, 'templates'), port: 0 });

    try {
      const response = await fetch(`http://localhost:${server.port}/page.html`);
      await expect(response.text()).resolves.toContain('/__ssg_live_reload');
    } finally {
      await server.close();
    }
  });
});
