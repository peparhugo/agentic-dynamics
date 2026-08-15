import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/generator';
import {
  loadTemplates,
  renderIndexTemplate,
  renderPageTemplate,
} from '../src/templates';
import { Page } from '../src/types';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-tpl-test-'));
}

async function write(dir: string, name: string, content: string): Promise<void> {
  const full = path.join(dir, name);
  await fs.mkdir(path.dirname(full), { recursive: true });
  await fs.writeFile(full, content, 'utf8');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'post',
    title: 'My Post',
    date: '2024-02-02',
    tags: ['tech'],
    content: '# Body',
    html: '<h1>Body</h1>',
    sourcePath: 'post.md',
    ...overrides,
  };
}

async function writeTemplateTree(
  templatesDir: string
): Promise<void> {
  await write(templatesDir, 'default.hbs', `<h2>{{title}}</h2>\n{{{html}}}`);
  await write(templatesDir, 'post.hbs', `<article><h2>{{title}}</h2>\n{{{html}}}</article>`);
  await write(templatesDir, 'index.hbs', `<ul>\n{{#each pages}}\n<li><a href="{{slug}}.html">{{title}}</a></li>\n{{/each}}\n</ul>`);
  await write(
    templatesDir,
    'layouts/default.hbs',
    `<!DOCTYPE html>\n<html lang="en">\n<head><title>{{title}}</title></head>\n<body>\n{{> header}}\n{{{body}}}\n{{> footer}}\n</body>\n</html>`
  );
  await write(templatesDir, 'partials/header.hbs', '<header><nav>Site Nav</nav></header>');
  await write(templatesDir, 'partials/footer.hbs', '<footer>Footer</footer>');
}

describe('loadTemplates', () => {
  it('reports missing directories as absent', async () => {
    const root = await makeTempDir();
    const bundle = await loadTemplates(path.join(root, 'templates'));
    expect(bundle.exists).toBe(false);
  });

  it('loads templates, layouts, and partials', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await writeTemplateTree(templatesDir);

    const bundle = await loadTemplates(templatesDir);
    expect(bundle.exists).toBe(true);
    expect(bundle.templates.has('default')).toBe(true);
    expect(bundle.templates.has('post')).toBe(true);
    expect(bundle.templates.has('index')).toBe(true);
    expect(bundle.layouts.has('default')).toBe(true);
    expect(bundle.partials.has('header')).toBe(true);
    expect(bundle.partials.has('footer')).toBe(true);
    expect(bundle.defaultTemplate).toBe('default');
    expect(bundle.defaultLayout).toBe('default');
    expect(bundle.hasIndexTemplate).toBe(true);
  });

  it('leaves defaults unset when optional files are missing', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'post.hbs', 'hello');

    const bundle = await loadTemplates(templatesDir);
    expect(bundle.exists).toBe(true);
    expect(bundle.defaultTemplate).toBeNull();
    expect(bundle.defaultLayout).toBeNull();
  });
});

describe('renderPageTemplate', () => {
  it('renders a page through its template and exposes page data', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'post.hbs', '<h2>{{title}}</h2>\n{{{html}}}');

    const bundle = await loadTemplates(templatesDir);
    const page = makePage({ template: 'post' });
    const html = renderPageTemplate(page, bundle);

    expect(html).toContain('<h2>My Post</h2>');
    expect(html).toContain('<h1>Body</h1>');
  });

  it('falls back to the default template when none is specified', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'DEFAULT {{title}}');

    const bundle = await loadTemplates(templatesDir);
    const html = renderPageTemplate(makePage(), bundle);
    expect(html).toBe('DEFAULT My Post');
  });

  it('uses the page template over the default template', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'DEFAULT {{title}}');
    await write(templatesDir, 'post.hbs', 'POST {{title}}');

    const bundle = await loadTemplates(templatesDir);
    const html = renderPageTemplate(makePage({ template: 'post' }), bundle);
    expect(html).toBe('POST My Post');
  });

  it('wraps content in the default layout at the {{{body}}} placeholder', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'CONTENT');
    await write(templatesDir, 'layouts/default.hbs', '<html><body>{{{body}}}</body></html>');

    const bundle = await loadTemplates(templatesDir);
    const html = renderPageTemplate(makePage(), bundle);
    expect(html).toBe('<html><body>CONTENT</body></html>');
  });

  it('supports a per-page layout from frontmatter', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'CONTENT');
    await write(templatesDir, 'layouts/default.hbs', '<default>{{{body}}}</default>');
    await write(templatesDir, 'layouts/wide.hbs', '<wide>{{{body}}}</wide>');

    const bundle = await loadTemplates(templatesDir);
    const page = makePage({ template: 'default', layout: 'wide' });
    const html = renderPageTemplate(page, bundle);
    expect(html).toBe('<wide>CONTENT</wide>');
  });

  it('renders partials inside templates and layouts', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await writeTemplateTree(templatesDir);

    const bundle = await loadTemplates(templatesDir);
    const html = renderPageTemplate(makePage({ template: 'post' }), bundle);

    expect(html).toContain('<header><nav>Site Nav</nav></header>');
    expect(html).toContain('<footer>Footer</footer>');
    expect(html).toContain('<article><h2>My Post</h2>');
    expect(html.indexOf('<header>')).toBeLessThan(html.indexOf('<article>'));
    expect(html.indexOf('</article>')).toBeLessThan(html.indexOf('<footer>'));
  });

  it('exposes arbitrary frontmatter data to templates', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'post.hbs', 'By {{author}} on {{date}}');

    const bundle = await loadTemplates(templatesDir);
    const page = makePage({
      template: 'post',
      data: { author: 'Ada', date: '2024-02-02' },
    });
    const html = renderPageTemplate(page, bundle);
    expect(html).toBe('By Ada on 2024-02-02');
  });

  it('escapes double-stashed values and allows raw triple-stashed HTML', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'post.hbs', '{{author}}|{{{author}}}');

    const bundle = await loadTemplates(templatesDir);
    const page = makePage({
      template: 'post',
      data: { author: '<b>Ada</b>' },
    });
    const html = renderPageTemplate(page, bundle);
    expect(html).toBe('&lt;b&gt;Ada&lt;/b&gt;|<b>Ada</b>');
  });

  it('throws when the named template cannot be found', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'post.hbs', 'x');

    const bundle = await loadTemplates(templatesDir);
    expect(() =>
      renderPageTemplate(makePage({ template: 'missing' }), bundle)
    ).toThrow('template not found: missing');
  });

  it('throws when the named layout cannot be found', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'x');

    const bundle = await loadTemplates(templatesDir);
    expect(() =>
      renderPageTemplate(makePage({ layout: 'nope' }), bundle)
    ).toThrow('layout not found: nope');
  });

  it('throws when there is no template directory at all', async () => {
    const root = await makeTempDir();
    const bundle = await loadTemplates(path.join(root, 'templates'));
    expect(() => renderPageTemplate(makePage({ template: 'post' }), bundle)).toThrow(
      'templates directory not found'
    );
  });
});

describe('renderIndexTemplate', () => {
  it('returns null when no index template exists', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'post.hbs', 'x');

    const bundle = await loadTemplates(templatesDir);
    expect(renderIndexTemplate([makePage()], bundle)).toBeNull();
  });

  it('renders pages with the index template and default layout', async () => {
    const root = await makeTempDir();
    const templatesDir = path.join(root, 'templates');
    await writeTemplateTree(templatesDir);

    const bundle = await loadTemplates(templatesDir);
    const html = renderIndexTemplate(
      [
        makePage({ slug: 'one', title: 'One' }),
        makePage({ slug: 'two', title: 'Two' }),
      ],
      bundle
    );

    expect(html).not.toBeNull();
    expect(html).toContain('<li><a href="one.html">One</a></li>');
    expect(html).toContain('<li><a href="two.html">Two</a></li>');
    expect(html).toContain('<header><nav>Site Nav</nav></header>');
    expect(html).toContain('<footer>Footer</footer>');
  });
});

describe('build with templates', () => {
  it('builds pages with templates, layouts, and partials', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await writeTemplateTree(templatesDir);

    await write(contentDir, 'hello.md', [
      '---',
      'title: Hello',
      'date: 2024-01-01',
      'template: post',
      '---',
      '# Hello',
      'World',
    ].join('\n'));
    await write(contentDir, 'plain.md', [
      '---',
      'title: Plain',
      '---',
      '# Plain',
    ].join('\n'));

    const pages = await build({ contentDir, outputDir, templatesDir });
    expect(pages).toHaveLength(2);

    const helloHtml = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(helloHtml).toContain('<article><h2>Hello</h2>');
    expect(helloHtml).toContain('<h1>Hello</h1>');
    expect(helloHtml).toContain('<header><nav>Site Nav</nav></header>');
    expect(helloHtml).toContain('<footer>Footer</footer>');

    const plainHtml = await fs.readFile(path.join(outputDir, 'plain.html'), 'utf8');
    expect(plainHtml).toContain('<h2>Plain</h2>');

    const indexHtml = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('<li><a href="hello.html">Hello</a></li>');
    expect(indexHtml).toContain('<li><a href="plain.html">Plain</a></li>');
  });

  it('uses default template when a page specifies no template', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'DEFAULT {{title}}: {{{html}}}');

    await write(contentDir, 'a.md', [
      '---',
      'title: A',
      '---',
      '# A',
    ].join('\n'));

    await build({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toBe('DEFAULT A: <h1>A</h1>\n');
  });

  it('keeps existing behavior when no templates directory exists', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await write(contentDir, 'hello.md', [
      '---',
      'title: Hello',
      'date: 2024-01-01',
      'tags: a, b',
      '---',
      '# Hello',
      'World',
    ].join('\n'));

    const pages = await build({ contentDir, outputDir, templatesDir: path.join(root, 'templates') });
    expect(pages).toHaveLength(1);

    const helloHtml = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(helloHtml).toContain('<h1>Hello</h1>');
    expect(helloHtml).toContain('World');
    expect(helloHtml).toContain('2024-01-01');

    const indexHtml = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('href="hello.html"');
    expect(indexHtml).toContain('<h1>Index</h1>');
  });

  it('throws when a page names a template that does not exist', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await write(templatesDir, 'default.hbs', 'x');

    await write(contentDir, 'a.md', [
      '---',
      'template: missing',
      '---',
      '# A',
    ].join('\n'));

    await expect(
      build({ contentDir, outputDir, templatesDir })
    ).rejects.toThrow('template not found: missing');
  });
});
