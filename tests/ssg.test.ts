import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown } from '../src';

describe('static site generator', () => {
  it('parses frontmatter and Markdown', async () => {
    const page = await parseMarkdown('---\ntitle: Hello\ndate: 2024-01-01\ntags: [news, intro]\n---\n\n**Welcome**', 'hello.md');
    expect(page.title).toBe('Hello');
    expect(page.date).toBe('2024-01-01');
    expect(page.tags).toEqual(['news', 'intro']);
    expect(page.html).toContain('<strong>Welcome</strong>');
  });

  it('builds pages and an index, including nested Markdown files', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(content, 'guide'), { recursive: true });
    await fs.writeFile(path.join(content, 'home.md'), '# Home');
    await fs.writeFile(path.join(content, 'guide', 'start.md'), '---\ntitle: Start\n---\nBegin');
    const pages = await buildSite({ contentDir: content, outputDir: output });
    expect(pages).toHaveLength(2);
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('guide/start.html');
    expect(await fs.readFile(path.join(output, 'guide', 'start.html'), 'utf8')).toContain('<h1>Start</h1>');
  });

  it('renders a Handlebars template inside a layout with partials', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello <world>\ntemplate: article\nlayout: site\ntags: [news]\n---\nWelcome');
    await fs.writeFile(path.join(templates, 'article.hbs'), '{{> header}}<article><h1>{{title}}</h1>{{{html}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'site.hbs'), '<!doctype html><body>{{{body}}}{{> footer}}</body>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    const result = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(result).toContain('<header>Header</header>');
    expect(result).toContain('<h1>Hello &lt;world&gt;</h1>');
    expect(result).toContain('<p>Welcome</p>');
    expect(result).toContain('<footer>Footer</footer>');
  });

  it('supports EJS defaults and unescaped layout body output', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'page.md'), '---\ntitle: EJS page\n---\nText');
    await fs.writeFile(path.join(templates, 'default.ejs'), '<main><%- html %><%- include("nav") %></main>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.ejs'), '<html><head><title><%= title %></title></head><body><%- body %></body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'nav.ejs'), '<nav>Nav</nav>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    const result = await fs.readFile(path.join(output, 'page.html'), 'utf8');
    expect(result).toContain('<title>EJS page</title>');
    expect(result).toContain('<p>Text</p>');
    expect(result).toContain('<nav>Nav</nav>');
  });
});
