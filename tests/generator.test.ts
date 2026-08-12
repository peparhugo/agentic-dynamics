import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown } from '../src/generator';

describe('static site generator', () => {
  it('parses frontmatter and markdown', async () => {
    const page = await parseMarkdown('/tmp/hello-world.md', '---\ntitle: Hello\ndate: 2024-01-02\ntags: [news, intro]\n---\n\n## Welcome\n\n**world**');
    expect(page.frontmatter).toEqual({ title: 'Hello', date: '2024-01-02', tags: ['news', 'intro'] });
    expect(page.html).toContain('<h2>Welcome</h2>');
    expect(page.outputPath).toBe('hello-world.html');
  });

  it('builds an index and nested pages', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'about.md'), '---\ntitle: About\n---\nAbout us.');
    await fs.writeFile(path.join(content, 'notes', 'first.md'), '# First');
    await buildSite({ contentDir: content, outputDir: output });
    expect(await fs.readFile(path.join(output, 'about.html'), 'utf8')).toContain('<title>About</title>');
    expect(await fs.readFile(path.join(output, 'notes', 'first.html'), 'utf8')).toContain('<h1>First</h1>');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="about.html"');
    expect(index).toContain('href="notes/first.html"');
  });

  it('renders a selected template inside a layout with partials', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'dist');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'post.md'), '---\ntitle: A Post\ntemplate: article\nlayout: site\n---\n\nHello **there**.');
    await fs.writeFile(path.join(templates, 'article.hbs'), '{{> nav}}<article><h1>{{title}}</h1>{{{body}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'site.hbs'), '<!doctype html><html><body>{{> header}}{{{body}}}{{> footer}}</body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');
    await fs.writeFile(path.join(templates, 'partials', 'nav.hbs'), '<nav>Nav</nav>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    const rendered = await fs.readFile(path.join(output, 'post.html'), 'utf8');
    expect(rendered).toContain('<header>Header</header>');
    expect(rendered).toContain('<nav>Nav</nav>');
    expect(rendered).toContain('<strong>there</strong>');
    expect(rendered).toContain('<footer>Footer</footer>');
  });

  it('uses default.hbs when a page has no template', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'dist');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(templates, { recursive: true });
    await fs.writeFile(path.join(content, 'home.md'), '# Welcome');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<main data-title="{{title}}">{{{content}}}</main>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });
    expect(await fs.readFile(path.join(output, 'home.html'), 'utf8')).toBe(
      '<main data-title="Home"><h1>Welcome</h1>\n</main>',
    );
  });
});
