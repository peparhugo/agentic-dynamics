import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/site.js';

describe('buildSite', () => {
  let directory: string;

  beforeEach(async () => {
    directory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(directory, { recursive: true, force: true });
  });

  it('renders frontmatter, markdown, nested pages, and an ordered index', async () => {
    const content = path.join(directory, 'content');
    const output = path.join(directory, 'dist');
    await fs.mkdir(path.join(content, 'guides'), { recursive: true });
    await fs.writeFile(path.join(content, 'welcome.md'), '---\ntitle: Welcome <Site>\ndate: 2025-01-02\ntags: [news, start]\n---\n# Hello\n\n**World**');
    await fs.writeFile(path.join(content, 'guides', 'install.md'), '---\ntitle: Install\ndate: 2025-02-03\n---\nInstallation text');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages.map((page) => page.title)).toEqual(['Install', 'Welcome <Site>']);
    await expect(fs.readFile(path.join(output, 'welcome.html'), 'utf8')).resolves.toContain('<h1>Welcome &lt;Site&gt;</h1>');
    await expect(fs.readFile(path.join(output, 'welcome.html'), 'utf8')).resolves.toContain('<strong>World</strong>');
    await expect(fs.readFile(path.join(output, 'guides', 'install.html'), 'utf8')).resolves.toContain('Installation text');
    await expect(fs.readFile(path.join(output, 'index.html'), 'utf8')).resolves.toContain('href="/guides/install.html"');
  });

  it('uses the filename as a title when frontmatter omits one', async () => {
    const content = path.join(directory, 'content');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'untitled.md'), 'Plain text');

    const pages = await buildSite({ contentDir: content, outputDir: path.join(directory, 'dist') });

    expect(pages[0].title).toBe('untitled');
  });

  it('renders the selected template inside a layout with partials', async () => {
    const content = path.join(directory, 'content');
    const templates = path.join(directory, 'templates');
    const output = path.join(directory, 'dist');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'custom.md'), '---\ntitle: Custom\ntemplate: article\n---\nTemplate **content**');
    await fs.writeFile(path.join(templates, 'article.hbs'), '<article><h1>{{title}}</h1>{{{body}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<!doctype html><body>{{> header}}<main>{{{body}}}</main>{{> footer}}</body>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    await expect(fs.readFile(path.join(output, 'custom.html'), 'utf8')).resolves.toBe('<!doctype html><body><header>Header</header><main><article><h1>Custom</h1><p>Template <strong>content</strong></p>\n</article></main><footer>Footer</footer></body>');
  });

  it('uses the default template when frontmatter does not specify one', async () => {
    const content = path.join(directory, 'content');
    const templates = path.join(directory, 'templates');
    const output = path.join(directory, 'dist');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'default.md'), '---\ntitle: Default\n---\nText');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<h1>{{title}}</h1>{{{body}}}');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    await expect(fs.readFile(path.join(output, 'default.html'), 'utf8')).resolves.toContain('<h1>Default</h1><p>Text</p>');
  });
});
