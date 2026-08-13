import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator.js';

describe('buildSite', () => {
  it('renders frontmatter, markdown pages, and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'site');
    await mkdir(content);
    await writeFile(join(content, 'hello.md'), '---\ntitle: Hello <World>\ndate: 2026-08-13\ntags:\n  - news\n  - typescript\n---\n\n# Welcome\n\nThis is **strong**.');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await readFile(join(output, 'hello.html'), 'utf8');
    const index = await readFile(join(output, 'index.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(page).toContain('<title>Hello &lt;World&gt;</title>');
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>strong</strong>');
    expect(page).not.toContain('---');
    expect(page).toContain('Tags: news, typescript');
    expect(index).toContain('href="hello.html"');
    expect(index).toContain('Hello &lt;World&gt;');
  });

  it('renders Handlebars page templates, layouts, and partials', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'site');
    await mkdir(content);
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'));
    await writeFile(join(content, 'hello.md'), '---\ntitle: Template page\ntemplate: article\nlayout: site\n---\n\nHello **world**.');
    await writeFile(join(templates, 'article.hbs'), '<article><h1>{{title}}</h1>{{> header}}{{{content}}}</article>');
    await writeFile(join(templates, 'layouts', 'site.hbs'), '<!doctype html><body>{{{body}}}{{> footer}}</body>');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });
    const page = await readFile(join(output, 'hello.html'), 'utf8');

    expect(page).toContain('<h1>Template page</h1>');
    expect(page).toContain('<header>Header</header>');
    expect(page).toContain('<strong>world</strong>');
    expect(page).toContain('<footer>Footer</footer>');
  });

  it('uses page and default layout templates when frontmatter omits them', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'site');
    await mkdir(content);
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await writeFile(join(content, 'hello.md'), '---\ntitle: Default template\n---\n\nContent');
    await writeFile(join(templates, 'page.hbs'), '<main>{{title}}: {{{content}}}</main>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toBe('<html><main>Default template: <p>Content</p>\n</main></html>');
  });
});
