import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from '../src/generate';
import { createTemplateEngine } from '../src/engine';
import type { Page } from '../src/types';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'hello',
    title: 'Hello',
    tags: ['one', 'two'],
    html: '<p>body</p>',
    ...overrides,
  };
}

describe('template engine', () => {
  it('renders a page with the built-in layout and page template', async () => {
    const templates = await makeTempDir();
    const engine = await createTemplateEngine(templates);

    const html = engine.renderPage(makePage());
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<p>body</p>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('one');
  });

  it('renders the index with the built-in template', async () => {
    const templates = await makeTempDir();
    const engine = await createTemplateEngine(templates);

    const html = engine.renderIndex([makePage()]);
    expect(html).toContain('<title>Index</title>');
    expect(html).toContain('hello.html');
    expect(html).toContain('Hello');
  });
});

describe('buildSite with templates', () => {
  it('uses a page template selected via frontmatter', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.writeFile(
      path.join(templates, 'post.hbs'),
      '<section class="post">{{title}}{{{content}}}</section>'
    );
    await fs.writeFile(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\ntemplate: post\n---\n# Welcome\n'
    );

    await buildSite(content, output, templates);

    const html = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(html).toContain('<section class="post">Hello');
    expect(html).toContain('<h1>Welcome</h1>');
  });

  it('uses a layout template selected via frontmatter with {{{body}}}', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.mkdir(path.join(templates, 'layouts'));
    await fs.writeFile(
      path.join(templates, 'layouts', 'fancy.hbs'),
      '<html><head><title>{{title}}</title></head><body class="fancy">{{{body}}}</body></html>'
    );
    await fs.writeFile(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\nlayout: fancy\n---\n# Welcome\n'
    );

    await buildSite(content, output, templates);

    const html = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(html).toContain('<body class="fancy">');
    expect(html).toContain('<h1>Welcome</h1>');
    expect(html).toContain('<title>Hello</title>');
  });

  it('supports partials referenced via {{> name}}', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.mkdir(path.join(templates, 'layouts'));
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.writeFile(
      path.join(templates, 'partials', 'header.hbs'),
      '<header class="site-header">Site</header>'
    );
    await fs.writeFile(
      path.join(templates, 'layouts', 'base.hbs'),
      '{{> header}}<main>{{{body}}}</main>'
    );
    await fs.writeFile(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\nlayout: base\n---\n# Welcome\n'
    );

    await buildSite(content, output, templates);

    const html = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(html).toContain('<header class="site-header">Site</header>');
    expect(html).toContain('<h1>Welcome</h1>');
  });

  it('uses a custom index template when present', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.writeFile(path.join(templates, 'index.hbs'), '<h1>My Site</h1>');
    await fs.writeFile(path.join(content, 'hello.md'), '# Hello\n');

    await buildSite(content, output, templates);

    const html = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(html).toContain('<h1>My Site</h1>');
  });

  it('falls back to built-in templates when a template is missing', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.writeFile(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\ntemplate: missing\nlayout: nope\n---\n# Welcome\n'
    );

    await buildSite(content, output, templates);

    const html = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<h1>Welcome</h1>');
  });

  it('lets a layout compose partials and page body together', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.mkdir(path.join(templates, 'layouts'));
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.writeFile(path.join(templates, 'partials', 'nav.hbs'), '<nav>Nav</nav>');
    await fs.writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Foot</footer>');
    await fs.writeFile(
      path.join(templates, 'layouts', 'page.hbs'),
      '{{> nav}}{{{body}}}{{> footer}}'
    );
    await fs.writeFile(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\nlayout: page\n---\n# Welcome\n'
    );

    await buildSite(content, output, templates);

    const html = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    expect(html).toContain('<nav>Nav</nav>');
    expect(html).toContain('<h1>Welcome</h1>');
    expect(html).toContain('<footer>Foot</footer>');
  });
});
