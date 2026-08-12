import { mkdtempSync, writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';
import {
  DEFAULT_LAYOUT_NAME,
  DEFAULT_TEMPLATE_DIR,
  DEFAULT_TEMPLATE_NAME,
  buildContext,
  TemplateEngine,
} from '../src/templates';
import type { Page } from '../src/types';

function makeTempDir(): string {
  return mkdtempSync(path.join(tmpdir(), 'ssg-tpl-test-'));
}

function writeFixture(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, content, 'utf8');
  }
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    title: 'Test',
    date: '2024-01-01',
    tags: ['a', 'b'],
    slug: 'test',
    source: 'test.md',
    html: '<p>Content</p>',
    ...overrides,
  };
}

describe('TemplateEngine.load', () => {
  it('loads templates, layouts, and partials from the templates directory', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/page.hbs': '<h1>{{title}}</h1>',
      'templates/default.hbs': '{{body}}',
      'templates/layouts/base.hbs': '<html>{{{body}}}</html>',
      'templates/partials/nav.hbs': '<nav>Nav</nav>',
    });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    expect(engine.hasTemplates()).toBe(true);
    expect(engine.hasTemplate('page')).toBe(true);
    expect(engine.hasTemplate('default')).toBe(true);
    expect(engine.hasLayout('base')).toBe(true);
    expect(engine.hasLayout('default')).toBe(false);
  });

  it('loads gracefully when the templates directory does not exist', async () => {
    const dir = makeTempDir();
    const engine = new TemplateEngine(path.join(dir, 'missing'));
    await engine.load();
    expect(engine.hasTemplates()).toBe(false);
  });
});

describe('TemplateEngine.renderTemplate', () => {
  it('renders page variables into a template', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/post.hbs':
        '<h1>{{title}}</h1>{{#if date}}<time datetime="{{date}}">{{date}}</time>{{/if}}<ul>{{#each tags}}<li>{{this}}</li>{{/each}}</ul>',
    });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    const context = buildContext(makePage(), '<p>Body</p>');
    const html = engine.renderTemplate('post', context);

    expect(html).toContain('<h1>Test</h1>');
    expect(html).toContain('<time datetime="2024-01-01">2024-01-01</time>');
    expect(html).toContain('<li>a</li>');
    expect(html).toContain('<li>b</li>');
  });

  it('throws a helpful error for a missing template', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'templates/default.hbs': '{{body}}' });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    expect(() => engine.renderTemplate('nope', buildContext(makePage(), ''))).toThrow('Template not found: nope');
  });
});

describe('TemplateEngine.renderPage', () => {
  it('uses the default template when a page does not specify one', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'templates/default.hbs': '<main>{{{body}}}</main>' });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    const html = engine.renderPage(makePage({ template: undefined }), '<p>Content</p>');
    expect(html).toContain('<main><p>Content</p></main>');
  });

  it('renders page content into a layout through the {{{body}}} placeholder', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/post.hbs': '<header><h1>{{title}}</h1></header><main>{{{body}}}</main>',
      'templates/layouts/base.hbs':
        '<!doctype html><html lang="en"><head><title>{{title}}</title></head><body>{{{body}}}</body></html>',
    });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    const page = makePage({ template: 'post', layout: 'base' });
    const html = engine.renderPage(page, '<p>Content</p>');

    expect(html).toContain('<title>Test</title>');
    expect(html).toContain('<header><h1>Test</h1></header>');
    expect(html).toContain('<main><p>Content</p></main>');
    expect(html.indexOf('<body>')).toBeLessThan(html.indexOf('<header>'));
  });

  it('applies a default layout when none is specified on the page', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/default.hbs': '<main>{{{body}}}</main>',
      'templates/layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
    });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    const html = engine.renderPage(makePage({ template: undefined, layout: undefined }), '<p>Content</p>');
    expect(html).toContain('<html><body><main><p>Content</p></main></body></html>');
  });

  it('includes partials from the partials directory', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/post.hbs': '{{> header}}{{> nav}}{{> footer}}<main>{{{body}}}</main>',
      'templates/partials/header.hbs': '<header>Site Header</header>',
      'templates/partials/nav.hbs': '<nav>Home</nav>',
      'templates/partials/footer.hbs': '<footer>Site Footer</footer>',
      'templates/layouts/base.hbs': '<html>{{{body}}}</html>',
    });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    const html = engine.renderPage(makePage({ template: 'post', layout: 'base' }), '<p>Content</p>');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<nav>Home</nav>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<html><header>Site Header</header>');
  });

  it('throws when a page references a missing layout', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/default.hbs': '{{body}}',
      'templates/layouts/base.hbs': '<html>{{{body}}}</html>',
    });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    expect(() => engine.renderPage(makePage({ layout: 'missing' }), '')).toThrow('Layout not found: missing');
  });

  it('exposes custom frontmatter fields to templates', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'templates/default.hbs': '{{author}} {{published}}' });

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    await engine.load();

    const page = makePage({ data: { author: 'Ada', published: true } });
    const html = engine.renderPage(page, '');
    expect(html).toContain('Ada true');
  });
});

describe('buildSite with templates', () => {
  it('renders pages through templates, layouts, and partials', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n# Hello\n',
      'templates/default.hbs':
        '{{> header}}<main><h1>{{title}}</h1>{{#if date}}<time>{{date}}</time>{{/if}}{{{body}}}</main>{{> footer}}',
      'templates/layouts/default.hbs': '<!doctype html><html lang="en"><head><title>{{title}}</title></head><body>{{{body}}}</body></html>',
      'templates/partials/header.hbs': '<header>Site Header</header>',
      'templates/partials/footer.hbs': '<footer>Site Footer</footer>',
    });

    const result = await buildSite(path.join(dir, 'content'), path.join(dir, 'dist'), {
      templatesDir: path.join(dir, 'templates'),
    });

    expect(result.files).toHaveLength(2);
    expect(existsSync(path.join(dir, 'dist', 'one.html'))).toBe(true);

    const html = readFileSync(path.join(dir, 'dist', 'one.html'), 'utf8');
    expect(html).toContain('<!doctype html>');
    expect(html).toContain('<title>One</title>');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<h1>One</h1>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<footer>Site Footer</footer>');
  });

  it('lets each page pick a template via frontmatter', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/featured.md': '---\ntitle: Featured\ntemplate: featured\n---\nBody',
      'content/plain.md': '---\ntitle: Plain\n---\nBody',
      'templates/default.hbs': '<p class="plain">{{title}}</p>{{{body}}}',
      'templates/featured.hbs': '<article class="featured">{{title}}{{{body}}}</article>',
      'templates/layouts/base.hbs': '<div class="layout">{{{body}}}</div>',
    });

    await buildSite(path.join(dir, 'content'), path.join(dir, 'dist'), {
      templatesDir: path.join(dir, 'templates'),
    });

    const featured = readFileSync(path.join(dir, 'dist', 'featured.html'), 'utf8');
    expect(featured).toContain('<article class="featured">Featured<p>Body</p>');
    expect(featured).toContain('</article>');
    expect(featured).not.toContain('class="plain"');

    const plain = readFileSync(path.join(dir, 'dist', 'plain.html'), 'utf8');
    expect(plain).toContain('<p class="plain">Plain</p>');
    expect(plain).not.toContain('<article class="featured">');
  });

  it('falls back to the built-in renderer when no templates exist', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\n# One\n',
    });

    const result = await buildSite(path.join(dir, 'content'), path.join(dir, 'dist'), {
      templatesDir: path.join(dir, 'missing-templates'),
    });

    const html = readFileSync(path.join(dir, 'dist', 'one.html'), 'utf8');
    expect(html).toContain('<h1>One</h1>');
    expect(result.files).toHaveLength(2);
  });

  it('throws a helpful error when a page requests a missing template', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\ntemplate: nope\n---\nBody',
      'templates/default.hbs': '{{body}}',
    });

    await expect(
      buildSite(path.join(dir, 'content'), path.join(dir, 'dist'), {
        templatesDir: path.join(dir, 'templates'),
      }),
    ).rejects.toThrow('Template not found: nope');
  });
});

describe('constants', () => {
  it('exposes default names and directory', () => {
    expect(DEFAULT_TEMPLATE_NAME).toBe('default');
    expect(DEFAULT_LAYOUT_NAME).toBe('default');
    expect(DEFAULT_TEMPLATE_DIR).toBe('templates');
  });
});
