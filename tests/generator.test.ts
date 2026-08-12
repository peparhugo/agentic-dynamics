import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  it('renders frontmatter Markdown and an index', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'notes', 'hello.md'), '---\ntitle: Hello\ndate: 2026-01-02\ntags: [one, two]\n---\n\n**Welcome**');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'notes', 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');

    expect(pages[0]).toMatchObject({ title: 'Hello', date: '2026-01-02', tags: ['one', 'two'] });
    expect(page).toContain('<strong>Welcome</strong>');
    expect(page).toContain('<title>Hello</title>');
    expect(index).toContain('href="notes/hello.html"');
  });

  it('renders a Handlebars template, layout, and partial', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'dist');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Templated\ntemplate: article\nlayout: site\n---\n\nHello **world**');
    await fs.writeFile(path.join(templates, 'article.hbs'), '<main><h1>{{title}}</h1>{{{content}}}</main>');
    await fs.writeFile(path.join(templates, 'layouts', 'site.hbs'), '<!doctype html><body>{{> header}} {{{body}}}</body>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>Site header</header>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');

    expect(page).toBe('<!doctype html><body><header>Site header</header> <main><h1>Templated</h1><p>Hello <strong>world</strong></p>\n</main></body>');
  });

  it('supports EJS templates and partial includes', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'dist');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: EJS page\ntemplate: page.ejs\n---\n\nText');
    await fs.writeFile(path.join(templates, 'page.ejs'), '<%- include("header") %><h1><%= title %></h1><%- content %>');
    await fs.writeFile(path.join(templates, 'partials', 'header.ejs'), '<header>Header</header>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');

    expect(page).toBe('<header>Header</header><h1>EJS page</h1><p>Text</p>\n');
  });

  it('skips unchanged pages and rebuilds only changed pages', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(content, { recursive: true });
    await fs.writeFile(path.join(content, 'one.md'), '---\ntitle: One\n---\n\nFirst');
    await fs.writeFile(path.join(content, 'two.md'), '---\ntitle: Two\n---\n\nSecond');

    const first = await buildSite({ contentDir: content, outputDir: output });
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(JSON.parse(await fs.readFile(path.join(output, '.ssg-cache.json'), 'utf8')).entries).toHaveProperty('one.md');

    await fs.writeFile(path.join(content, 'one.md'), '---\ntitle: One changed\n---\n\nUpdated');
    const second = await buildSite({ contentDir: content, outputDir: output, incremental: true });
    expect(second.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(await fs.readFile(path.join(output, 'one.html'), 'utf8')).toContain('One changed');
    expect(await fs.readFile(path.join(output, 'two.html'), 'utf8')).toContain('Second');
  });

  it('invalidates every page when a template changes', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'dist');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(templates, { recursive: true });
    await fs.writeFile(path.join(content, 'one.md'), '---\ntitle: One\ntemplate: page\n---\n\nFirst');
    await fs.writeFile(path.join(content, 'two.md'), '---\ntitle: Two\ntemplate: page\n---\n\nSecond');
    await fs.writeFile(path.join(templates, 'page.hbs'), '<h1>{{title}}</h1>{{{content}}}');
    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    await fs.writeFile(path.join(templates, 'page.hbs'), '<h2>{{title}}</h2>{{{content}}}');

    const result = await buildSite({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(result.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(await fs.readFile(path.join(output, 'one.html'), 'utf8')).toContain('<h2>One</h2>');
  });
});
