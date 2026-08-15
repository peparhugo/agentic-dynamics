import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseArgs, parseMarkdown } from '../index';

describe('markdown parsing', () => {
  it('parses simple YAML frontmatter and merges it with gray-matter output', () => {
    const parsed = parseMarkdown('---\ntitle: Hello world\ndate: 2026-01-02\ntags: [news, typescript]\n---\n\n# Heading');
    expect(parsed.data).toEqual({ title: 'Hello world', date: '2026-01-02', tags: ['news', 'typescript'] });
    expect(parsed.content).toContain('# Heading');
  });

  it('parses documents without frontmatter', () => {
    expect(parseMarkdown('# Plain').data).toEqual({});
  });
});

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
    await fs.mkdir(path.join(root, 'content', 'notes'), { recursive: true });
    await fs.writeFile(path.join(root, 'content', 'first.md'), '---\ntitle: First\ndate: 2026-02-01\n---\n\n**Hello**');
    await fs.writeFile(path.join(root, 'content', 'notes', 'second.markdown'), '# Second');
  });

  it('writes pages and an index using configured directories', async () => {
    const output = path.join(root, 'public');
    const pages = await buildSite({ contentDir: path.join(root, 'content'), outputDir: output });
    expect(pages.map((page) => page.outputPath)).toEqual(['first.html', 'notes/second.html']);
    expect(await fs.readFile(path.join(output, 'first.html'), 'utf8')).toContain('<strong>Hello</strong>');
    expect(await fs.readFile(path.join(output, 'notes', 'second.html'), 'utf8')).toContain('<h1>Second</h1>');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="first.html"');
    expect(index).toContain('href="notes/second.html"');
  });

  it('renders a selected template, layout, and partials', async () => {
    const templates = path.join(root, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(templates, 'article.hbs'), '{{> header}}<article><h1>{{title}}</h1>{{{body}}}</article>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<html><body>{{{body}}}<footer>Footer</footer></body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{siteName}}</header>');
    await fs.writeFile(path.join(root, 'content', 'first.md'), '---\ntitle: Custom\ntemplate: article\nsiteName: Example\n---\n\n**Content**');

    const output = path.join(root, 'public');
    await buildSite({ contentDir: path.join(root, 'content'), outputDir: output, templatesDir: templates });
    const page = await fs.readFile(path.join(output, 'first.html'), 'utf8');
    expect(page).toContain('<html><body><header>Example</header><article><h1>Custom</h1>');
    expect(page).toContain('<p><strong>Content</strong></p>');
    expect(page).toContain('<footer>Footer</footer></body></html>');
  });

  it('uses the default template when a page does not select one', async () => {
    const templates = path.join(root, 'templates');
    await fs.mkdir(templates, { recursive: true });
    await fs.writeFile(path.join(templates, 'default.hbs'), '<main>{{title}} {{{body}}}</main>');
    const output = path.join(root, 'public');
    await buildSite({ contentDir: path.join(root, 'content'), outputDir: output, templatesDir: templates });
    expect(await fs.readFile(path.join(output, 'notes', 'second.html'), 'utf8')).toContain('<main>Second <h1>Second</h1>');
  });
});

describe('CLI arguments', () => {
  it('parses build directory options', () => {
    expect(parseArgs(['--content', 'articles', '--output', 'site', '--templates', 'theme'])).toEqual({ contentDir: 'articles', outputDir: 'site', templatesDir: 'theme' });
  });
});
