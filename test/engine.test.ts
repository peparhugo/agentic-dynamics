import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  TemplateEngine,
  DEFAULT_LAYOUT_NAME,
  DEFAULT_TEMPLATE_NAME,
  LAYOUT_DIR,
  PARTIALS_DIR,
} from '../src/engine';
import type { Page } from '../src/types';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-engine-'));
}

function writeFiles(root: string, files: Record<string, string>): void {
  for (const [name, contents] of Object.entries(files)) {
    const file = path.join(root, name);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, contents, 'utf-8');
  }
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'post',
    sourcePath: 'post.md',
    data: {},
    body: '# Hello',
    html: '<h1>Hello</h1>',
    outputFile: 'post.html',
    ...overrides,
  };
}

describe('TemplateEngine', () => {
  let root: string;

  beforeEach(() => {
    root = makeTempDir();
  });

  afterEach(() => {
    cleanup(root);
  });

  it('throws when the templates directory does not exist', () => {
    expect(() => new TemplateEngine(path.join(root, 'missing'))).toThrow(
      'templates directory not found',
    );
  });

  it('hasTemplate reflects files in the templates directory', () => {
    writeFiles(root, { 'post.hbs': '{{title}}' });
    const engine = new TemplateEngine(root);
    expect(engine.hasTemplate('post')).toBe(true);
    expect(engine.hasTemplate('missing')).toBe(false);
  });

  it('renders frontmatter data into the page template context', () => {
    writeFiles(root, { 'post.hbs': '<h1>{{title}}</h1><time>{{date}}</time>{{{body}}}' });
    const engine = new TemplateEngine(root);

    const page = makePage({
      data: { template: 'post', title: 'My Post', date: '2024-05-10' },
      html: '<p>content</p>',
    });

    const html = engine.renderPage(page);
    expect(html).toContain('<h1>My Post</h1>');
    expect(html).toContain('<time>2024-05-10</time>');
    expect(html).toContain('<p>content</p>');
  });

  it('falls back to the slug title when no title is set', () => {
    writeFiles(root, { 'default.hbs': '{{title}}' });
    const engine = new TemplateEngine(root);
    const html = engine.renderPage(makePage({ data: {} }));
    expect(html).toBe('post');
  });

  it('returns null when no template applies', () => {
    writeFiles(root, { 'other.hbs': 'ignored' });
    const engine = new TemplateEngine(root);
    expect(engine.renderPage(makePage())).toBeNull();
  });

  it('uses a per-page template selected from frontmatter', () => {
    writeFiles(root, {
      'default.hbs': 'DEFAULT-{{title}}',
      'post.hbs': 'POST-{{title}}',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ data: { template: 'post', title: 'T' } });
    expect(engine.renderPage(page)).toBe('POST-T');
  });

  it('wraps the page template in the default layout via {{{body}}}', () => {
    writeFiles(root, {
      'default.hbs': '<main class="page">{{{body}}}</main>',
      [`${LAYOUT_DIR}/${DEFAULT_LAYOUT_NAME}.hbs`]:
        '<html><head><title>{{title}}</title></head><body class="layout">{{{body}}}</body></html>',
    });
    const engine = new TemplateEngine(root);
    const html = engine.renderPage(makePage({ data: { title: 'T' }, html: '<p>body</p>' }));

    expect(html).toContain('class="layout"');
    expect(html).toContain('<main class="page">');
    expect(html).toContain('<title>T</title>');
    expect(html).toContain('<p>body</p>');
  });

  it('lets a page template declare its layout in frontmatter', () => {
    writeFiles(root, {
      'post.hbs': '---\nlayout: base\n---\n<article>{{{body}}}</article>',
      [`${LAYOUT_DIR}/base.hbs`]: '<div class="base">{{{body}}}</div>',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ data: { template: 'post' }, html: '<p>x</p>' });
    const html = engine.renderPage(page);

    expect(html).toContain('class="base"');
    expect(html).toContain('<article>');
    expect(html).toContain('<p>x</p>');
  });

  it('prefers the layout from page frontmatter over the template layout', () => {
    writeFiles(root, {
      'post.hbs': '---\nlayout: base\n---\n<article>{{{body}}}</article>',
      [`${LAYOUT_DIR}/base.hbs`]: '<div class="base">{{{body}}}</div>',
      [`${LAYOUT_DIR}/bare.hbs`]: '<div class="bare">{{{body}}}</div>',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ data: { template: 'post', layout: 'bare' }, html: '<p>x</p>' });
    const html = engine.renderPage(page);

    expect(html).toContain('class="bare"');
    expect(html).not.toContain('class="base"');
  });

  it('falls back to the default layout when the named layout is missing', () => {
    writeFiles(root, {
      'default.hbs': '<main>{{{body}}}</main>',
      [`${LAYOUT_DIR}/${DEFAULT_LAYOUT_NAME}.hbs`]: '<div class="fallback">{{{body}}}</div>',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ data: { layout: 'nope' }, html: '<p>x</p>' });
    const html = engine.renderPage(page);
    expect(html).toContain('class="fallback"');
    expect(html).toContain('<p>x</p>');
  });

  it('returns the page template output when no layout applies', () => {
    writeFiles(root, { 'default.hbs': '<main>{{{body}}}</main>' });
    const engine = new TemplateEngine(root);
    const html = engine.renderPage(makePage({ html: '<p>x</p>' }));
    expect(html).toBe('<main><p>x</p></main>');
  });

  it('renders partials registered from the partials directory', () => {
    writeFiles(root, {
      'default.hbs': '{{> header}}{{{body}}}{{> footer}}',
      [`${PARTIALS_DIR}/header.hbs`]: '<header>Site Header</header>',
      [`${PARTIALS_DIR}/footer.hbs`]: '<footer>Site Footer</footer>',
    });
    const engine = new TemplateEngine(root);
    const html = engine.renderPage(makePage({ html: '<p>x</p>' }));

    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<p>x</p>');
  });

  it('exposes site pages for navigation partials', () => {
    writeFiles(root, {
      'default.hbs':
        '<nav>{{#each site.pages}}<a href="./{{outputFile}}">{{title}}</a>{{/each}}</nav>{{{body}}}',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ html: '<p>x</p>' });
    const html = engine.renderPage(page, {
      pages: [
        { slug: 'about', title: 'About', outputFile: 'about.html' },
        { slug: 'post', title: 'Post', outputFile: 'post.html' },
      ],
    });

    expect(html).toContain('<a href="./about.html">About</a>');
    expect(html).toContain('<a href="./post.html">Post</a>');
  });

  it('escapes interpolated values with {{ }} and renders raw with {{{ }}}', () => {
    writeFiles(root, {
      'default.hbs': '{{title}}|{{{title}}}',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ data: { title: '<b>x</b>' } });
    const html = engine.renderPage(page);
    expect(html).toContain('&lt;b&gt;x&lt;/b&gt;|<b>x</b>');
  });

  it('falls back to the default template when the named template is missing', () => {
    writeFiles(root, {
      'default.hbs': 'DEFAULT-{{title}}',
      'post.hbs': 'POST-{{title}}',
    });
    const engine = new TemplateEngine(root);
    const page = makePage({ data: { template: 'ghost', title: 'T' } });
    expect(engine.renderPage(page)).toBe('DEFAULT-T');
  });
});

describe('template constants', () => {
  it('exposes the conventional template names', () => {
    expect(DEFAULT_TEMPLATE_NAME).toBe('default');
    expect(DEFAULT_LAYOUT_NAME).toBe('default');
    expect(LAYOUT_DIR).toBe('layouts');
    expect(PARTIALS_DIR).toBe('partials');
  });
});
