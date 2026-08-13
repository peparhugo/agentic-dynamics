import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { TemplateEngine } from '../src/templateEngine';
import { Page } from '../src/types';

function makeTmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-template-test-'));
}

function writeFile(filePath: string, contents: string) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, contents, 'utf-8');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    sourcePath: 'hello.md',
    slug: 'hello',
    outputFile: 'hello.html',
    title: 'Hello',
    date: '2024-01-01',
    tags: ['a', 'b'],
    html: '<p>Body</p>',
    template: undefined,
    ...overrides,
  };
}

describe('TemplateEngine', () => {
  let templatesDir: string;

  beforeEach(() => {
    templatesDir = makeTmpDir();
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('returns undefined for renderPage when no layouts exist', () => {
    const engine = new TemplateEngine(templatesDir);
    expect(engine.renderPage(makePage(), [])).toBeUndefined();
  });

  it('returns undefined for renderIndex when no layouts exist', () => {
    const engine = new TemplateEngine(templatesDir);
    expect(engine.renderIndex([])).toBeUndefined();
  });

  it('renders a page through the default layout, substituting {{{body}}}', () => {
    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage(makePage(), []);

    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<p>Body</p>');
  });

  it('selects a layout named in the page frontmatter `template` field', () => {
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<div class="default">{{{body}}}</div>');
    writeFile(path.join(templatesDir, 'layouts', 'post.hbs'), '<div class="post-layout">{{{body}}}</div>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage(makePage({ template: 'post' }), []);

    expect(html).toContain('class="post-layout"');
    expect(html).not.toContain('class="default"');
  });

  it('falls back to the default layout when the requested template is missing', () => {
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<div class="default">{{{body}}}</div>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage(makePage({ template: 'does-not-exist' }), []);

    expect(html).toContain('class="default"');
  });

  it('includes header, nav and footer partials in layout output', () => {
    writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>MY HEADER</header>');
    writeFile(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>MY NAV</nav>');
    writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>MY FOOTER</footer>');
    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '{{> header}}{{> nav}}<main>{{{body}}}</main>{{> footer}}'
    );

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage(makePage(), []);

    expect(html).toContain('MY HEADER');
    expect(html).toContain('MY NAV');
    expect(html).toContain('MY FOOTER');
  });

  it('renders {{> header}}/{{> nav}}/{{> footer}} as empty strings when partial files are absent', () => {
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '[{{> header}}][{{{body}}}][{{> footer}}]');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage(makePage(), []);

    expect(html).toContain('[][');
  });

  it('renders the index page through the "index" layout with a page listing body', () => {
    writeFile(
      path.join(templatesDir, 'layouts', 'index.hbs'),
      '<title>{{title}}</title><main>{{{body}}}</main>'
    );

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderIndex([makePage()]);

    expect(html).toContain('<title>Home</title>');
    expect(html).toContain('href="hello.html"');
  });

  it('falls back to the default layout for the index page when no index layout exists', () => {
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<div class="default-index">{{{body}}}</div>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderIndex([makePage()]);

    expect(html).toContain('class="default-index"');
    expect(html).toContain('href="hello.html"');
  });
});
