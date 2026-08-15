import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { buildSite, parsePage } from './site';
import type { Plugin } from './plugin';
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
  it('incrementally skips unchanged pages and invalidates cached output for source and template changes', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-incremental-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'output');
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(content);
    const first = join(content, 'first.md');
    const second = join(content, 'second.md');
    await writeFile(first, '---\ntitle: First\n---\n\nOne');
    await writeFile(second, '---\ntitle: Second\n---\n\nTwo');
    await writeFile(join(templates, 'default.hbs'), '<article>{{title}} {{{content}}}</article>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');

    const initialStats: { pagesBuilt: number; pagesSkipped: number }[] = [];
    await buildSite({ contentDir: content, outputDir: output, templateDir: templates, incremental: true, onStats: (stats) => initialStats.push(stats) });
    expect(initialStats[0]).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(readFile(join(root, '.ssg-cache.json'), 'utf8')).resolves.toContain('first.md');

    const unchangedStats: { pagesBuilt: number; pagesSkipped: number }[] = [];
    await buildSite({ contentDir: content, outputDir: output, templateDir: templates, incremental: true, onStats: (stats) => unchangedStats.push(stats) });
    expect(unchangedStats[0]).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });

    await writeFile(first, '---\ntitle: Updated\n---\n\nOne');
    const changedStats: { pagesBuilt: number; pagesSkipped: number }[] = [];
    await buildSite({ contentDir: content, outputDir: output, templateDir: templates, incremental: true, onStats: (stats) => changedStats.push(stats) });
    expect(changedStats[0]).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    await expect(readFile(join(output, 'first.html'), 'utf8')).resolves.toContain('Updated');

    await rm(join(output, 'second.html'));
    const restoredStats: { pagesBuilt: number; pagesSkipped: number }[] = [];
    await buildSite({ contentDir: content, outputDir: output, templateDir: templates, incremental: true, onStats: (stats) => restoredStats.push(stats) });
    expect(restoredStats[0]).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    await expect(readFile(join(output, 'second.html'), 'utf8')).resolves.toContain('Second');

    await writeFile(join(templates, 'default.hbs'), '<section>{{title}} {{{content}}}</section>');
    const templateStats: { pagesBuilt: number; pagesSkipped: number }[] = [];
    await buildSite({ contentDir: content, outputDir: output, templateDir: templates, incremental: true, onStats: (stats) => templateStats.push(stats) });
    expect(templateStats[0]).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(readFile(join(output, 'second.html'), 'utf8')).resolves.toContain('<section>Second');
  });

  it('runs configured plugin hooks in order and lets plugins modify pages before rendering', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-plugin-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    const calls: string[] = [];
    const plugin: Plugin = {
      onStart: () => { calls.push('start'); },
      beforeBuild: () => { calls.push('before'); },
      onFile: (context) => { calls.push('file'); if (context.page) context.page.title = 'Modified'; },
      afterBuild: () => { calls.push('after'); },
      onEnd: () => { calls.push('end'); },
    };
    await mkdir(content);
    await writeFile(join(content, 'page.md'), '# Page');

    await buildSite({ contentDir: content, outputDir: output, plugins: [plugin] });

    expect(calls).toEqual(['start', 'before', 'file', 'after', 'end']);
    await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>Modified</h1>');
  });

  it('loads plugins from ssg.config.ts', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-config-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    const config = join(root, 'ssg.config.ts');
    await mkdir(content);
    await writeFile(join(content, 'page.md'), '# Page');
    await writeFile(config, 'export default { plugins: [{ onFile(context: { page?: { title: string } }) { if (context.page) context.page.title = "Configured"; } }] };');

    await buildSite({ contentDir: content, outputDir: output, configFile: config });

    await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>Configured</h1>');
  });

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
