import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite, buildSiteWithStats, parseMarkdown } from '../src/generator';

describe('static site generator', () => {
  it('parses YAML frontmatter and markdown', () => {
    const page = parseMarkdown('---\ntitle: Hello World\ndate: 2024-01-02\ntags: [news, intro]\n---\n\n**Welcome**', 'hello.md');
    expect(page.title).toBe('Hello World');
    expect(page.date).toBe('2024-01-02');
    expect(page.tags).toEqual(['news', 'intro']);
    expect(page.html).toContain('<strong>Welcome</strong>');
  });

  it('builds an index and one HTML file per markdown page', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'first.md'), '---\ntitle: First\ndate: 2024-02-01\n---\nFirst page');
    await fs.writeFile(path.join(content, 'second.md'), '# Second');

    const pages = await buildSite(content, output);
    expect(pages.map((page) => page.title)).toEqual(['First', 'Second']);
    expect(await fs.readFile(path.join(output, 'first.html'), 'utf8')).toContain('<h1>First</h1>');
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('second.html');
  });

  it('renders a selected Handlebars template inside a layout with partials', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.writeFile(path.join(content, 'welcome.md'), '---\ntitle: Welcome\ntemplate: article\n---\n**Hello**');
    await fs.writeFile(path.join(templates, 'article.hbs'), '{{> header}}<article>{{{html}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<!doctype html><body>{{{body}}}{{> footer}}</body>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>End</footer>');

    await buildSite(content, output, templates);
    const html = await fs.readFile(path.join(output, 'welcome.html'), 'utf8');
    expect(html).toBe('<!doctype html><body><header>Welcome</header><article><p><strong>Hello</strong></p>\n</article><footer>End</footer></body>');
  });

  it('uses the default EJS template when a page has no template', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(content, 'page.md'), '---\ntitle: EJS Page\n---\nContent');
    await fs.writeFile(path.join(templates, 'default.ejs'), '<h1><%= title %></h1><%- html %>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.ejs'), '<html><body><%- body %></body></html>');

    await buildSite(content, output, templates);
    expect(await fs.readFile(path.join(output, 'page.html'), 'utf8')).toBe('<html><body><h1>EJS Page</h1><p>Content</p>\n</body></html>');
  });

  it('skips unchanged pages and rebuilds only changed sources', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'first.md'), '# First');
    await fs.writeFile(path.join(content, 'second.md'), '# Second');

    const initial = await buildSiteWithStats(content, output, undefined, { incremental: true });
    expect(initial.stats.pagesBuilt).toBe(2);
    expect(initial.stats.pagesSkipped).toBe(0);
    expect(JSON.parse(await fs.readFile(path.join(output, '.ssg-cache.json'), 'utf8')).pages['first.md'].sourceHash).toBeTruthy();

    const unchanged = await buildSiteWithStats(content, output, undefined, { incremental: true });
    expect(unchanged.stats.pagesBuilt).toBe(0);
    expect(unchanged.stats.pagesSkipped).toBe(2);

    await fs.writeFile(path.join(content, 'second.md'), '# Second changed');
    const changed = await buildSiteWithStats(content, output, undefined, { incremental: true });
    expect(changed.stats.pagesBuilt).toBe(1);
    expect(changed.stats.pagesSkipped).toBe(1);
    expect(await fs.readFile(path.join(output, 'second.html'), 'utf8')).toContain('Second changed');
    expect(await fs.readFile(path.join(output, 'first.html'), 'utf8')).toContain('<h1>First</h1>');
  });

  it('rebuilds all pages when a template changes or a clean build is requested', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'one.md'), '# One');
    await fs.writeFile(path.join(content, 'two.md'), '# Two');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<article>{{{html}}}</article>');

    await buildSiteWithStats(content, output, templates, { incremental: true });
    expect((await buildSiteWithStats(content, output, templates, { incremental: true })).stats.pagesSkipped).toBe(2);
    await fs.writeFile(path.join(templates, 'default.hbs'), '<section>{{{html}}}</section>');
    const templateChanged = await buildSiteWithStats(content, output, templates, { incremental: true });
    expect(templateChanged.stats.pagesBuilt).toBe(2);
    expect(await fs.readFile(path.join(output, 'one.html'), 'utf8')).toContain('<section>');

    const clean = await buildSiteWithStats(content, output, templates, { incremental: true, clean: true });
    expect(clean.stats.pagesBuilt).toBe(2);
    expect(clean.stats.pagesSkipped).toBe(0);
  });
});
