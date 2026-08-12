import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    await fs.mkdir(path.join(root, 'content', 'notes'), { recursive: true });
    await fs.writeFile(
      path.join(root, 'content', 'welcome.md'),
      ['---', 'title: Welcome', 'date: 2025-01-02', 'tags:', '  - intro', '  - ssg', '---', '# Hello', '', 'This is **Markdown**.'].join('\n'),
    );
    await fs.writeFile(path.join(root, 'content', 'notes', 'second.markdown'), '---\ntitle: Second\n---\nA second page.');
  });

  it('converts Markdown and frontmatter into page documents', async () => {
    const pages = await buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') });
    const output = await fs.readFile(path.join(root, 'dist', 'welcome.html'), 'utf8');
    expect(pages).toHaveLength(2);
    expect(output).toContain('<title>Welcome</title>');
    expect(output).toContain('<h1>Hello</h1>');
    expect(output).toContain('<li>intro</li>');
    expect(output).toContain('2025-01-02');
  });

  it('creates an index and preserves nested output paths', async () => {
    await buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') });
    const index = await fs.readFile(path.join(root, 'dist', 'index.html'), 'utf8');
    expect(index).toContain('welcome.html');
    expect(index).toContain('notes/second.html');
    await expect(fs.access(path.join(root, 'dist', 'notes', 'second.html'))).resolves.toBeUndefined();
  });

  it('uses the filename when a title is not provided', async () => {
    await fs.writeFile(path.join(root, 'content', 'untitled.md'), 'Plain text');
    await buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') });
    const output = await fs.readFile(path.join(root, 'dist', 'untitled.html'), 'utf8');
    expect(output).toContain('<title>untitled</title>');
  });

  it('renders a selected template, layout, and partials', async () => {
    await fs.mkdir(path.join(root, 'templates', 'layouts'), { recursive: true });
    await fs.mkdir(path.join(root, 'templates', 'partials'), { recursive: true });
    await fs.writeFile(path.join(root, 'templates', 'article.hbs'), '{{> header}}<article>{{{body}}}</article>');
    await fs.writeFile(path.join(root, 'templates', 'layouts', 'site.hbs'), '<html><body>{{{body}}}</body></html>');
    await fs.writeFile(path.join(root, 'templates', 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(
      path.join(root, 'content', 'welcome.md'),
      '---\ntitle: Custom\ntemplate: article\nlayout: site\n---\n# Content',
    );

    await buildSite({
      contentDir: path.join(root, 'content'),
      outputDir: path.join(root, 'dist'),
      templatesDir: path.join(root, 'templates'),
    });
    const output = await fs.readFile(path.join(root, 'dist', 'welcome.html'), 'utf8');
    expect(output).toBe('<html><body><header>Custom</header><article><h1>Content</h1>\n</article></body></html>');
  });

  it('uses default EJS templates and escaped values', async () => {
    await fs.mkdir(path.join(root, 'templates'), { recursive: true });
    await fs.writeFile(path.join(root, 'templates', 'default.ejs'), '<h1><%= title %></h1><%- content %>');
    await fs.writeFile(path.join(root, 'content', 'special.md'), '---\ntitle: "A < B"\n---\n**safe**');

    await buildSite({
      contentDir: path.join(root, 'content'),
      outputDir: path.join(root, 'dist'),
      templatesDir: path.join(root, 'templates'),
    });
    const output = await fs.readFile(path.join(root, 'dist', 'special.html'), 'utf8');
    expect(output).toContain('<h1>A &lt; B</h1>');
    expect(output).toContain('<p><strong>safe</strong></p>');
  });

  it('incrementally rebuilds only changed pages and persists a cache manifest', async () => {
    const options = {
      contentDir: path.join(root, 'content'),
      outputDir: path.join(root, 'dist'),
      incremental: true,
    };

    const first = await buildSite(options);
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.access(path.join(root, '.ssg-cache.json'))).resolves.toBeUndefined();

    const second = await buildSite(options);
    expect(second.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });

    await fs.writeFile(path.join(root, 'content', 'welcome.md'), '---\ntitle: Changed\n---\n# Updated');
    const third = await buildSite(options);
    expect(third.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(await fs.readFile(path.join(root, 'dist', 'welcome.html'), 'utf8')).toContain('Changed');
    expect(await fs.readFile(path.join(root, 'dist', 'notes', 'second.html'), 'utf8')).toContain('Second');
  });

  it('invalidates every page when a template changes and supports clean builds', async () => {
    const options = {
      contentDir: path.join(root, 'content'),
      outputDir: path.join(root, 'dist'),
      templatesDir: path.join(root, 'templates'),
      incremental: true,
    };
    await fs.mkdir(options.templatesDir, { recursive: true });
    await fs.writeFile(path.join(options.templatesDir, 'default.ejs'), '<h1><%= title %></h1><%- content %>');
    await buildSite(options);
    expect((await buildSite(options)).stats.pagesSkipped).toBe(2);

    await fs.writeFile(path.join(options.templatesDir, 'default.ejs'), '<main><%= title %></main>');
    expect((await buildSite(options)).stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });

    await fs.writeFile(path.join(root, 'dist', 'stale.txt'), 'stale');
    await buildSite({ ...options, clean: true });
    await expect(fs.access(path.join(root, 'dist', 'stale.txt'))).rejects.toThrow();
  });
});
