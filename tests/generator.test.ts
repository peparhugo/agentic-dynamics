import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  it('writes pages and an index using supplied directories', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello & goodbye\ntags: [one, two]\n---\n\n**Welcome**');
    await fs.writeFile(path.join(content, 'notes', 'second.md'), '# Second');

    await buildSite({ contentDir: content, outputDir: output });

    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    const nested = await fs.readFile(path.join(output, 'notes', 'second.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(page).toContain('<title>Hello &amp; goodbye</title>');
    expect(page).toContain('<strong>Welcome</strong>');
    expect(page).toContain('one, two');
    expect(nested).toContain('<h1>second</h1>');
    expect(index).toContain('hello.html');
    expect(index).toContain('notes/second.html');
  });

  it('renders a selected Handlebars template inside a layout with partials', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello\ntemplate: article\nlayout: site\n---\n\nWelcome');
    await fs.writeFile(path.join(templates, 'article.hbs'), '{{> nav}}<section>{{{body}}}</section>');
    await fs.writeFile(path.join(templates, 'layouts', 'site.hbs'), '<html><body>{{> header}}{{{body}}}{{> footer}}</body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');
    await fs.writeFile(path.join(templates, 'partials', 'nav.hbs'), '<nav>Nav</nav>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });

    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(page).toContain('<header>Hello</header>');
    expect(page).toContain('<nav>Nav</nav><section><article>');
    expect(page).toContain('<footer>Footer</footer>');
  });

  it('supports EJS templates and includes', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: EJS page\ntemplate: page.ejs\n---\n\nHello');
    await fs.writeFile(path.join(templates, 'page.ejs'), '<%- include("partials/header") %><h2><%= title %></h2><%- body %>');
    await fs.writeFile(path.join(templates, 'partials', 'header.ejs'), '<header>Header</header>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });

    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(page).toContain('<header>Header</header><h2>EJS page</h2>');
    expect(page).toContain('<p>Hello</p>');
  });
});
