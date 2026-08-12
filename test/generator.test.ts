import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  test('builds Markdown pages and an index from frontmatter', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await mkdir(path.join(content, 'notes'), { recursive: true });
    await writeFile(path.join(content, 'welcome.md'), '---\ntitle: Welcome\ndate: 2026-01-01\ntags: [intro, news]\n---\n\n# Hello\n\nThis is **Markdown**.');
    await writeFile(path.join(content, 'notes', 'second.md'), '# Second');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages).toHaveLength(2);
    expect(await readFile(path.join(output, 'welcome.html'), 'utf8')).toContain('<h1>Welcome</h1>');
    expect(await readFile(path.join(output, 'welcome.html'), 'utf8')).toContain('<strong>Markdown</strong>');
    expect(await readFile(path.join(output, 'notes', 'second.html'), 'utf8')).toContain('<h1>Second</h1>');
    expect(await readFile(path.join(output, 'index.html'), 'utf8')).toContain('href="/welcome.html"');
    expect(await readFile(path.join(output, 'index.html'), 'utf8')).toContain('href="/notes/second.html"');
  });

  test('removes stale generated files', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await mkdir(content, { recursive: true });
    await mkdir(output, { recursive: true });
    await writeFile(path.join(output, 'old.html'), 'old');
    await writeFile(path.join(content, 'page.md'), '---\ntitle: Page\n---\nContent');

    await buildSite({ contentDir: content, outputDir: output });

    await expect(readFile(path.join(output, 'old.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test('renders a Handlebars template, layout, and partials from frontmatter', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    await mkdir(content, { recursive: true });
    await mkdir(path.join(templates, 'layouts'), { recursive: true });
    await mkdir(path.join(templates, 'partials'), { recursive: true });
    await writeFile(path.join(templates, 'article.hbs'), '<h1>{{title}}</h1>{{{content}}}{{> footer}}');
    await writeFile(path.join(templates, 'layouts', 'site.hbs'), '<!doctype html><body>{{> header}}{{{body}}}</body>');
    await writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');
    await writeFile(path.join(content, 'page.md'), '---\ntitle: Templated\ntemplate: article\nlayout: site\n---\nHello **world**');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = await readFile(path.join(output, 'page.html'), 'utf8');
    expect(html).toContain('<header>Header</header>');
    expect(html).toContain('<h1>Templated</h1>');
    expect(html).toContain('<strong>world</strong>');
    expect(html).toContain('<footer>Footer</footer>');
  });

  test('uses the default EJS template when no template is in frontmatter', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    await mkdir(content, { recursive: true });
    await mkdir(path.join(templates, 'partials'), { recursive: true });
    await writeFile(path.join(templates, 'default.ejs'), '<main><h1><%= title %></h1><%- content %><%- include("partials/footer") %></main>');
    await writeFile(path.join(templates, 'partials', 'footer.ejs'), '<footer>Included</footer>');
    await writeFile(path.join(content, 'page.md'), '---\ntitle: Default\n---\nText');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    expect(await readFile(path.join(output, 'page.html'), 'utf8')).toBe('<main><h1>Default</h1><p>Text</p>\n<footer>Included</footer></main>');
  });
});
