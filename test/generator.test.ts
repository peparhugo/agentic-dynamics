import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator';
import { parseArguments } from '../src/cli';
import { startDevServer } from '../src/server';

describe('buildSite', () => {
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
});

describe('parseArguments', () => {
  it('accepts custom content and output directories', () => {
    expect(parseArguments(['--content', 'posts', '--output', 'public', '--templates', 'views'])).toEqual({ contentDir: 'posts', outputDir: 'public', templatesDir: 'views' });
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
