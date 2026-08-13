import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { escapeHtml, renderIndex, renderPage, TemplateEngine } from '../src/templates';
import { Page } from '../src/types';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-templates-'));
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    title: 'Sample Page',
    date: '2026-01-01',
    tags: ['a', 'b'],
    slug: 'sample-page',
    sourcePath: '/content/sample-page.md',
    outputPath: 'sample-page.html',
    html: '<p>Body</p>',
    ...overrides,
  };
}

describe('escapeHtml', () => {
  it('escapes html special characters', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });
});

describe('renderPage with built-in defaults', () => {
  let engine: TemplateEngine;

  beforeEach(() => {
    // Point at a directory that does not exist so the engine falls back
    // to its built-in default template and layout.
    engine = new TemplateEngine(path.join(os.tmpdir(), 'ssg-nonexistent-templates-dir'));
  });

  it('includes the title, date, tags, and content', () => {
    const html = renderPage(makePage(), engine);

    expect(html).toContain('<title>Sample Page</title>');
    expect(html).toContain('<h1>Sample Page</h1>');
    expect(html).toContain('2026-01-01');
    expect(html).toContain('<li>a</li>');
    expect(html).toContain('<li>b</li>');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('href="index.html"');
  });

  it('escapes untrusted title content', () => {
    const html = renderPage(makePage({ title: '<img src=x onerror=alert(1)>' }), engine);
    expect(html).not.toContain('<img src=x onerror=alert(1)>');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('omits the tag list when there are no tags', () => {
    const html = renderPage(makePage({ tags: [] }), engine);
    expect(html).not.toContain('class="tags"');
  });
});

describe('renderIndex with built-in defaults', () => {
  let engine: TemplateEngine;

  beforeEach(() => {
    engine = new TemplateEngine(path.join(os.tmpdir(), 'ssg-nonexistent-templates-dir'));
  });

  it('lists every page sorted by date descending', () => {
    const pages = [
      makePage({ title: 'Older', date: '2026-01-01', outputPath: 'older.html' }),
      makePage({ title: 'Newer', date: '2026-03-01', outputPath: 'newer.html' }),
    ];

    const html = renderIndex(pages, engine);
    const newerIndex = html.indexOf('Newer');
    const olderIndex = html.indexOf('Older');

    expect(newerIndex).toBeGreaterThan(-1);
    expect(olderIndex).toBeGreaterThan(-1);
    expect(newerIndex).toBeLessThan(olderIndex);
    expect(html).toContain('href="newer.html"');
    expect(html).toContain('href="older.html"');
  });

  it('renders an empty list when there are no pages', () => {
    const html = renderIndex([], engine);
    expect(html).toContain('<ul class="pages">');
  });
});

describe('TemplateEngine with a custom templates directory', () => {
  let dir: string;

  beforeEach(() => {
    dir = makeTempDir();
    fs.mkdirSync(path.join(dir, 'layouts'));
    fs.mkdirSync(path.join(dir, 'partials'));
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('uses the default page template and layout when none are named on disk', () => {
    const engine = new TemplateEngine(dir);
    const html = renderPage(makePage(), engine);
    expect(html).toContain('<h1>Sample Page</h1>');
    expect(html).toContain('<p>Body</p>');
  });

  it('selects a custom template named in page frontmatter', () => {
    fs.writeFileSync(
      path.join(dir, 'custom.hbs'),
      '<section class="custom">{{title}}: {{{content}}}</section>'
    );

    const engine = new TemplateEngine(dir);
    const html = renderPage(makePage({ template: 'custom' }), engine);

    expect(html).toContain('<section class="custom">Sample Page: <p>Body</p></section>');
  });

  it('throws a clear error when a named template file is missing', () => {
    const engine = new TemplateEngine(dir);
    expect(() => renderPage(makePage({ template: 'missing' }), engine)).toThrow(
      /Template not found/
    );
  });

  it('wraps rendered page content in the layout at the {{{body}}} placeholder', () => {
    fs.writeFileSync(
      path.join(dir, 'layouts', 'default.hbs'),
      '<div id="before"></div>{{{body}}}<div id="after"></div>'
    );

    const engine = new TemplateEngine(dir);
    const html = renderPage(makePage(), engine);

    expect(html).toContain('<div id="before"></div>');
    expect(html).toContain('<div id="after"></div>');
    expect(html.indexOf('<div id="before"></div>')).toBeLessThan(html.indexOf('<h1>Sample Page</h1>'));
    expect(html.indexOf('<h1>Sample Page</h1>')).toBeLessThan(html.indexOf('<div id="after"></div>'));
  });

  it('selects a custom layout named in page frontmatter', () => {
    fs.writeFileSync(path.join(dir, 'layouts', 'minimal.hbs'), '<minimal>{{{body}}}</minimal>');

    const engine = new TemplateEngine(dir);
    const html = renderPage(makePage({ layout: 'minimal' }), engine);

    expect(html).toContain('<minimal>');
    expect(html).toContain('<h1>Sample Page</h1>');
    expect(html).not.toContain('<!DOCTYPE html>');
  });

  it('throws a clear error when a named layout file is missing', () => {
    const engine = new TemplateEngine(dir);
    expect(() => renderPage(makePage({ layout: 'missing' }), engine)).toThrow(/Layout not found/);
  });

  it('renders registered partials referenced from a template or layout', () => {
    fs.writeFileSync(path.join(dir, 'partials', 'header.hbs'), '<header>Site Header</header>');
    fs.writeFileSync(
      path.join(dir, 'layouts', 'default.hbs'),
      '{{> header}}{{{body}}}'
    );

    const engine = new TemplateEngine(dir);
    const html = renderPage(makePage(), engine);

    expect(html).toContain('<header>Site Header</header>');
  });

  it('supports multiple partials such as header, nav, and footer', () => {
    fs.writeFileSync(path.join(dir, 'partials', 'header.hbs'), '<header>H</header>');
    fs.writeFileSync(path.join(dir, 'partials', 'nav.hbs'), '<nav>N</nav>');
    fs.writeFileSync(path.join(dir, 'partials', 'footer.hbs'), '<footer>F</footer>');
    fs.writeFileSync(
      path.join(dir, 'layouts', 'default.hbs'),
      '{{> header}}{{> nav}}{{{body}}}{{> footer}}'
    );

    const engine = new TemplateEngine(dir);
    const html = renderPage(makePage(), engine);

    expect(html).toContain('<header>H</header>');
    expect(html).toContain('<nav>N</nav>');
    expect(html).toContain('<footer>F</footer>');
  });

  it('renders a custom index template through renderIndex', () => {
    fs.writeFileSync(
      path.join(dir, 'index.hbs'),
      '<ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
    );

    const engine = new TemplateEngine(dir);
    const html = renderIndex([makePage({ title: 'One' }), makePage({ title: 'Two' })], engine);

    expect(html).toContain('<li>One</li>');
    expect(html).toContain('<li>Two</li>');
  });
});
