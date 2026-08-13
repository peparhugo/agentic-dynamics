import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator';
import { parseArguments } from '../src/cli';

describe('static site generator', () => {
  it('renders Markdown pages and a frontmatter-powered index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'public');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'welcome.md'), '---\ntitle: Welcome\ndate: 2026-08-13\ntags:\n  - news\n---\n\n# Hello\n\nA **site**.\n');
    await writeFile(join(content, 'guides', 'start.md'), '# Start here\n');

    const pages = await buildSite({ content, output });

    expect(pages.map((page) => page.slug)).toEqual(['guides/start', 'welcome']);
    await expect(readFile(join(output, 'welcome.html'), 'utf8')).resolves.toContain('<strong>site</strong>');
    await expect(readFile(join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<h1>start</h1>');
    const index = await readFile(join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="/welcome.html">Welcome</a>');
    expect(index).toContain('href="/guides/start.html">start</a>');
  });

  it('parses build directory options', () => {
    expect(parseArguments(['--content', 'posts', '--output', 'site', '--templates', 'views'])).toEqual({ content: 'posts', output: 'site', templates: 'views' });
    expect(() => parseArguments(['--content'])).toThrow('--content requires a directory');
  });

  it('renders frontmatter templates inside layouts with partials', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'public');
    await mkdir(content, { recursive: true });
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'), { recursive: true });
    await writeFile(join(content, 'post.md'), '---\ntitle: Template post\ntemplate: post\nlayout: site\n---\n\nTemplate **content**.\n');
    await writeFile(join(content, 'default.md'), '---\ntitle: Default post\n---\n\nDefault content.\n');
    await writeFile(join(templates, 'post.hbs'), '{{> header}}<section class="post">{{title}}: {{{html}}}</section>{{> footer}}');
    await writeFile(join(templates, 'default.hbs'), '<section class="default">{{title}}: {{{html}}}</section>');
    await writeFile(join(templates, 'layouts', 'site.hbs'), '<!doctype html><html><body>{{{body}}}</body></html>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<main class="default-layout">{{{body}}}</main>');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>Header</header>');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ content, output, templates });

    await expect(readFile(join(output, 'post.html'), 'utf8')).resolves.toContain('<header>Header</header><section class="post">Template post: <p>Template <strong>content</strong>.</p>');
    await expect(readFile(join(output, 'post.html'), 'utf8')).resolves.toContain('<footer>Footer</footer>');
    await expect(readFile(join(output, 'default.html'), 'utf8')).resolves.toContain('<section class="default">Default post: <p>Default content.</p>');
    await expect(readFile(join(output, 'default.html'), 'utf8')).resolves.toContain('<main class="default-layout">');
  });
});
