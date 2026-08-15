import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { buildSite, parsePage } from './site';
import { startDevServer } from './server';

describe('parsePage', () => {
  it('parses simple YAML frontmatter and renders Markdown', () => {
    const page = parsePage('---\ntitle: Hello World\ndate: 2026-08-15\ntags: [typescript, static]\n---\n\n# Welcome', 'hello-world.md');

    expect(page).toMatchObject({ title: 'Hello World', date: '2026-08-15', tags: ['typescript', 'static'], slug: 'hello-world' });
    expect(page.html).toContain('<h1>Welcome</h1>');
    expect(page.template).toBeUndefined();
  });

  it('uses the filename as a title when frontmatter has no title', () => {
    expect(parsePage('A page', 'my-page.md').title).toBe('my page');
  });
});

describe('buildSite', () => {
  it('creates a page HTML file and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(content);
    await writeFile(join(content, 'first-post.md'), '---\ntitle: First Post\ntags: news, updates\n---\n\nBody');

    await buildSite({ contentDir: content, outputDir: output });

    await expect(readFile(join(output, 'first-post.html'), 'utf8')).resolves.toContain('<h1>First Post</h1>');
    await expect(readFile(join(output, 'index.html'), 'utf8')).resolves.toContain('href="first-post.html"');
  });

  it('renders a page template inside a layout with partials', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-templates-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'output');
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'), { recursive: true });
    await mkdir(content);
    await writeFile(join(content, 'article.md'), '---\ntitle: Template Article\ntemplate: article\nlayout: site\nsection: Journal\n---\n\nBody');
    await writeFile(join(templates, 'article.hbs'), '<article><h1>{{title}}</h1><p>{{section}}</p>{{{content}}}</article>');
    await writeFile(join(templates, 'layouts', 'site.hbs'), '<!doctype html><body>{{> header}}<main>{{{body}}}</main>{{> footer}}</body>');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, outputDir: output, templateDir: templates });

    await expect(readFile(join(output, 'article.html'), 'utf8')).resolves.toBe('<!doctype html><body><header>Header</header><main><article><h1>Template Article</h1><p>Journal</p><p>Body</p>\n</article></main><footer>Footer</footer></body>');
  });

  it('uses default page and layout templates when frontmatter omits them', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-default-template-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'output');
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(content);
    await writeFile(join(content, 'plain.md'), '---\ntitle: Plain\n---\n\nText');
    await writeFile(join(templates, 'default.hbs'), '<article>{{title}}: {{{content}}}</article>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');

    await buildSite({ contentDir: content, outputDir: output, templateDir: templates });

    await expect(readFile(join(output, 'plain.html'), 'utf8')).resolves.toBe('<html><body><article>Plain: <p>Text</p>\n</article></body></html>');
  });
});

describe('development server', () => {
  it('serves generated pages with live reload and reloads after a content change', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-server-'));
    const content = join(root, 'content');
    const output = join(root, 'dist');
    await mkdir(content);
    const page = join(content, 'page.md');
    await writeFile(page, '---\ntitle: First\n---\n\nBody');

    const server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });
    const socket = new WebSocket(`ws://127.0.0.1:${server.port}`);
    try {
      await new Promise<void>((resolveOpen, reject) => {
        socket.once('open', resolveOpen);
        socket.once('error', reject);
      });
      const reload = new Promise<void>((resolveReload, reject) => {
        const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
        socket.once('message', () => {
          clearTimeout(timeout);
          resolveReload();
        });
      });

      const response = await fetch(`http://127.0.0.1:${server.port}/page.html`);
      expect(await response.text()).toContain('new WebSocket');
      await writeFile(page, '---\ntitle: Updated\n---\n\nBody');
      await reload;
      await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>Updated</h1>');
    } finally {
      socket.terminate();
      await server.close();
    }
  });
});
