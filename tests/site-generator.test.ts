import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { buildSite, parseMarkdown } from '../src/site-generator';

async function temporaryDirectory(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('parseMarkdown', () => {
  test('parses frontmatter and Markdown content', () => {
    const page = parseMarkdown(
      '---\ntitle: Hello World\ndate: 2024-01-02\ntags:\n  - typescript\n  - web\n---\n\n## Heading\n\n**content**',
      'hello.md',
    );

    expect(page.title).toBe('Hello World');
    expect(page.date).toBe('2024-01-02');
    expect(page.tags).toEqual(['typescript', 'web']);
    expect(page.outputPath).toBe('hello.html');
    expect(page.html).toContain('<h2>Heading</h2>');
    expect(page.html).toContain('<strong>content</strong>');
  });

  test('uses the filename when title is absent and accepts comma-separated tags', () => {
    const page = parseMarkdown('---\ntags: typescript, web\n---\n\nBody', 'notes.md');
    expect(page.title).toBe('notes');
    expect(page.tags).toEqual(['typescript', 'web']);
    expect(page.html).toContain('<p>Body</p>');
  });
});

describe('buildSite', () => {
  test('writes pages and an index, including nested Markdown files', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(content, 'guides'), { recursive: true });
    await fs.writeFile(path.join(content, 'first.md'), '---\ntitle: First\n---\nWelcome.');
    await fs.writeFile(path.join(content, 'guides', 'second.md'), '# Second');
    await fs.writeFile(path.join(content, 'skip.txt'), 'not Markdown');

    const result = await buildSite({ contentDir: content, outputDir: output });
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    const first = await fs.readFile(path.join(output, 'first.html'), 'utf8');
    const second = await fs.readFile(path.join(output, 'guides', 'second.html'), 'utf8');

    expect(result.pages).toHaveLength(2);
    expect(index).toContain('href="first.html"');
    expect(index).toContain('href="guides/second.html"');
    expect(index).toContain('First');
    expect(first).toContain('<h1>First</h1>');
    expect(first).toContain('<p>Welcome.</p>');
    expect(second).toContain('<h1>second</h1>');
    expect(second).toContain('<h1 id="second">Second</h1>');
  });

  test('creates an empty index for an empty content directory', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);

    const result = await buildSite({ contentDir: content, outputDir: output });
    expect(result.pages).toEqual([]);
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('<ul>');
  });

  test('renders a selected template, layout, and partials', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'welcome.md'), [
      '---', 'title: Welcome', 'template: article', 'layout: site', 'tags: one, two', '---', '', 'Hello **world**.',
    ].join('\n'));
    await fs.writeFile(path.join(templates, 'article.hbs'), '{{> header}}<article><h1>{{title}}</h1>{{{body}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'site.hbs'), '<!doctype html><html><body>{{{body}}}{{> footer}}</body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });
    const rendered = await fs.readFile(path.join(output, 'welcome.html'), 'utf8');

    expect(rendered).toBe('<!doctype html><html><body><header>Welcome</header><article><h1>Welcome</h1><p>Hello <strong>world</strong>.</p>\n</article><footer>Footer</footer></body></html>');
  });

  test('uses default.hbs when a template is not specified', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'page.md'), '---\ntitle: Custom\n---\nContent');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<h1>{{title}}</h1>{{{body}}}');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });
    expect(await fs.readFile(path.join(output, 'page.html'), 'utf8')).toBe('<h1>Custom</h1><p>Content</p>\n');
  });

  test('skips unchanged pages on an incremental build and restores cached HTML', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'one.md'), '# One');
    await fs.writeFile(path.join(content, 'two.md'), '# Two');

    const first = await buildSite({ contentDir: content, outputDir: output, incremental: true });
    const second = await buildSite({ contentDir: content, outputDir: output, incremental: true });

    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    expect(second.stats.timeSaved).toBeGreaterThan(0);
    expect(await fs.readFile(path.join(output, 'one.html'), 'utf8')).toContain('<h1 id="one">One</h1>');
    expect(JSON.parse(await fs.readFile(path.join(output, '.ssg-cache.json'), 'utf8')).pages['one.md']).toBeDefined();
  });

  test('rebuilds only changed pages and invalidates all pages when a template changes', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'one.md'), '# One');
    await fs.writeFile(path.join(content, 'two.md'), '# Two');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<article>{{{body}}}</article>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    await fs.writeFile(path.join(content, 'two.md'), '# Changed');
    const changed = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    expect(changed.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(await fs.readFile(path.join(output, 'two.html'), 'utf8')).toContain('Changed');

    await fs.writeFile(path.join(templates, 'default.hbs'), '<section>{{{body}}}</section>');
    const templateChanged = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    expect(templateChanged.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(await fs.readFile(path.join(output, 'one.html'), 'utf8')).toContain('<section>');
  });

  test('clean forces an incremental rebuild', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# Page');

    await buildSite({ contentDir: content, outputDir: output, incremental: true });
    const clean = await buildSite({ contentDir: content, outputDir: output, incremental: true, clean: true });
    expect(clean.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
  });
});
