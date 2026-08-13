import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { get } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/site';
import { startDevelopmentServer } from '../src/server';

describe('buildSite', () => {
  let workspace: string;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), 'ssg-test-'));
  });

  afterEach(() => {
    rmSync(workspace, { recursive: true, force: true });
  });

  it('renders Markdown, frontmatter, and an index page', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    mkdirSync(content);
    writeFileSync(join(content, 'welcome.md'), `---
title: Welcome <Home>
date: 2025-01-02
tags:
  - news
---
# Hello`);

    const pages = buildSite({ contentDir: content, outputDir: output });

    expect(pages).toHaveLength(1);
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<h1>Hello</h1>');
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<title>Welcome &lt;Home&gt;</title>');
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<span>news</span>');
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<time datetime="2025-01-02">2025-01-02</time>');
    expect(readFileSync(join(output, 'index.html'), 'utf8')).toContain('<a href="welcome.html">Welcome &lt;Home&gt;</a>');
  });

  it('preserves nested Markdown paths and uses a filename title when absent', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'dist');
    mkdirSync(join(content, 'guides'), { recursive: true });
    writeFileSync(join(content, 'guides', 'install.md'), 'Install instructions');

    const pages = buildSite({ contentDir: content, outputDir: output });

    expect(pages[0]).toMatchObject({ title: 'guides/install', url: 'guides/install.html' });
    expect(existsSync(join(output, 'guides', 'install.html'))).toBe(true);
    expect(readFileSync(join(output, 'index.html'), 'utf8')).toContain('href="guides/install.html"');
  });

  it('fails with a clear error for a missing content directory', () => {
    expect(() => buildSite({ contentDir: join(workspace, 'missing') })).toThrow('Content directory does not exist');
  });

  it('renders the default template inside the default layout with partials', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    const templates = join(workspace, 'templates');
    mkdirSync(join(templates, 'layouts'), { recursive: true });
    mkdirSync(join(templates, 'partials'), { recursive: true });
    mkdirSync(content);
    writeFileSync(join(content, 'welcome.md'), '---\ntitle: Welcome\n---\nHello **world**');
    writeFileSync(join(templates, 'default.hbs'), '<article><h1>{{title}}</h1>{{{content}}}</article>');
    writeFileSync(join(templates, 'layouts', 'default.hbs'), '<!doctype html><body>{{> header}}<main>{{{body}}}</main>{{> footer}}</body>');
    writeFileSync(join(templates, 'partials', 'header.hbs'), '<header>Site header</header>');
    writeFileSync(join(templates, 'partials', 'footer.hbs'), '<footer>Site footer</footer>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = readFileSync(join(output, 'welcome.html'), 'utf8');
    expect(html).toContain('<header>Site header</header>');
    expect(html).toContain('<article><h1>Welcome</h1><p>Hello <strong>world</strong></p>');
    expect(html).toContain('<footer>Site footer</footer>');
  });

  it('uses the template and layout selected in frontmatter', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    const templates = join(workspace, 'templates');
    mkdirSync(join(templates, 'layouts'), { recursive: true });
    mkdirSync(content);
    writeFileSync(join(content, 'product.md'), '---\ntitle: Product\ntemplate: product\nlayout: store\n---\nDetails');
    writeFileSync(join(templates, 'product.hbs'), '<section class="product">{{title}}: {{{content}}}</section>');
    writeFileSync(join(templates, 'layouts', 'store.hbs'), '<html><body class="store">{{{body}}}</body></html>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    expect(readFileSync(join(output, 'product.html'), 'utf8')).toBe('<html><body class="store"><section class="product">Product: <p>Details</p>\n</section></body></html>');
  });

  it('fails clearly when a selected template does not exist', () => {
    const content = join(workspace, 'content');
    mkdirSync(content);
    writeFileSync(join(content, 'missing.md'), '---\ntemplate: missing\n---\nContent');

    expect(() => buildSite({ contentDir: content, outputDir: join(workspace, 'public') })).toThrow('Template does not exist: missing');
  });

  it('only rebuilds changed pages during incremental builds', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    mkdirSync(content);
    writeFileSync(join(content, 'first.md'), '# First');
    writeFileSync(join(content, 'second.md'), '# Second');

    const initial = buildSite({ contentDir: content, outputDir: output, incremental: true });
    const unchanged = buildSite({ contentDir: content, outputDir: output, incremental: true });
    writeFileSync(join(content, 'first.md'), '# Updated');
    const changed = buildSite({ contentDir: content, outputDir: output, incremental: true });

    expect(initial.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    expect(unchanged.stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 2 }));
    expect(changed.stats).toEqual(expect.objectContaining({ pagesBuilt: 1, pagesSkipped: 1 }));
    expect(readFileSync(join(output, 'first.html'), 'utf8')).toContain('<h1>Updated</h1>');
    expect(existsSync(join(workspace, '.ssg-cache.json'))).toBe(true);
  });

  it('invalidates cached pages when templates change and removes deleted pages', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    const templates = join(workspace, 'templates');
    mkdirSync(content);
    mkdirSync(templates);
    writeFileSync(join(content, 'first.md'), '---\ntitle: First\n---\nContent');
    writeFileSync(join(content, 'second.md'), '---\ntitle: Second\n---\nContent');
    writeFileSync(join(templates, 'default.hbs'), '<article>{{title}}</article>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    writeFileSync(join(templates, 'default.hbs'), '<main>{{title}}</main>');
    const templated = buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    rmSync(join(content, 'second.md'));
    const deleted = buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    expect(templated.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    expect(readFileSync(join(output, 'first.html'), 'utf8')).toContain('<main>First</main>');
    expect(deleted.stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 1 }));
    expect(existsSync(join(output, 'second.html'))).toBe(false);
  });

  it('performs a clean incremental build when requested', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    mkdirSync(content);
    writeFileSync(join(content, 'page.md'), '# Page');

    buildSite({ contentDir: content, outputDir: output, incremental: true });
    const clean = buildSite({ contentDir: content, outputDir: output, incremental: true, clean: true });

    expect(clean.stats).toEqual(expect.objectContaining({ pagesBuilt: 1, pagesSkipped: 0 }));
    expect(readFileSync(join(output, 'page.html'), 'utf8')).toContain('<h1>Page</h1>');
  });
});

describe('startDevelopmentServer', () => {
  let workspace: string;
  let server: ReturnType<typeof startDevelopmentServer>;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), 'ssg-server-test-'));
    const content = join(workspace, 'content');
    mkdirSync(content);
    writeFileSync(join(content, 'welcome.md'), '---\ntitle: Welcome\n---\nHello');
    server = startDevelopmentServer({ contentDir: content, outputDir: join(workspace, 'dist'), port: 0 });
  });

  afterEach(async () => {
    await server.close();
    rmSync(workspace, { recursive: true, force: true });
  });

  it('serves generated pages with the live reload script', async () => {
    await new Promise<void>((resolve) => server.server.once('listening', resolve));
    const address = server.server.address();
    if (!address || typeof address === 'string') throw new Error('Server did not bind to a TCP port');
    const html = await new Promise<string>((resolve, reject) => {
      get(`http://localhost:${address.port}/welcome.html`, (response) => {
        let body = '';
        response.setEncoding('utf8');
        response.on('data', (chunk) => { body += chunk; });
        response.on('end', () => resolve(body));
      }).on('error', reject);
    });

    expect(html).toContain('new WebSocket');
    expect(html).toContain('/__ssg_reload');
  });
});
