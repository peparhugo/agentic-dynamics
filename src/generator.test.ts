import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from './generator';

describe('buildSite', () => {
  it('renders frontmatter Markdown pages and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'site');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'hello.md'), '---\ntitle: Hello World\ndate: 2026-08-13\ntags:\n  - welcome\n---\n# Hello\n\nA **site**.', 'utf8');
    await writeFile(join(content, 'guides', 'start.markdown'), '# Start here', 'utf8');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages).toEqual(expect.arrayContaining([
      expect.objectContaining({ title: 'Hello World', date: '2026-08-13', tags: ['welcome'], slug: 'hello.html' }),
      expect.objectContaining({ title: 'start', slug: 'guides/start.html' }),
    ]));
    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toContain('<h1>Hello</h1>');
    await expect(readFile(join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<h1>Start here</h1>');
    await expect(readFile(join(output, 'index.html'), 'utf8')).resolves.toContain('<a href="hello.html">Hello World</a>');
  });

  it('rejects a missing content directory', async () => {
    await expect(buildSite({ contentDir: join(tmpdir(), 'missing-ssg-content') })).rejects.toThrow('Content directory does not exist');
  });

  it('renders default and selected Handlebars templates inside layouts with partials', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'site');
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'), { recursive: true });
    await writeFile(join(content, 'default.md'), '---\ntitle: Default <Title>\n---\n# Default', 'utf8');
    await writeFile(join(content, 'custom.md'), '---\ntitle: Custom\ntemplate: article\nlayout: article\n---\n# Custom', 'utf8');
    await writeFile(join(templates, 'default.hbs'), '<article>{{title}} {{{content}}}</article>', 'utf8');
    await writeFile(join(templates, 'article.hbs'), '<section class="article">{{{content}}}</section>', 'utf8');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<!doctype html><body>{{> header}}<main>{{{body}}}</main>{{> footer}}</body>', 'utf8');
    await writeFile(join(templates, 'layouts', 'article.hbs'), '<html><body>{{> nav}} {{{body}}}</body></html>', 'utf8');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>', 'utf8');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>', 'utf8');
    await writeFile(join(templates, 'partials', 'nav.hbs'), '<nav>Navigation</nav>', 'utf8');

    await buildSite({ contentDir: content, outputDir: output, templateDir: templates });

    await expect(readFile(join(output, 'default.html'), 'utf8')).resolves.toBe(
      '<!doctype html><body><header>Default &lt;Title&gt;</header><main><article>Default &lt;Title&gt; <h1>Default</h1>\n</article></main><footer>Footer</footer></body>',
    );
    await expect(readFile(join(output, 'custom.html'), 'utf8')).resolves.toBe(
      '<html><body><nav>Navigation</nav> <section class="article"><h1>Custom</h1>\n</section></body></html>',
    );
  });
});
