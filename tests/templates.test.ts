import fs from 'fs';
import os from 'os';
import path from 'path';
import { getTemplateEngine, TemplateEngine } from '../src/templates';
import { Page } from '../src/types';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function makeSamplePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'sample',
    title: 'Sample Page',
    date: '2024-05-01',
    tags: ['a', 'b'],
    html: '',
    outputPath: 'sample.html',
    template: 'default',
    ...overrides,
  };
}

describe('TemplateEngine', () => {
  let templatesDir: string;

  beforeEach(() => {
    templatesDir = makeTmpDir('ssg-templates-');
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.mkdirSync(path.join(templatesDir, 'partials'));
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('renders a page using the default layout when no template is specified', () => {
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );
    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage({ title: 'Hello', tags: [], body: '<p>Body</p>' });
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<p>Body</p>');
  });

  it('selects an alternate layout by name', () => {
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<div class="default">{{{body}}}</div>');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'post.hbs'), '<div class="post">{{{body}}}</div>');
    const engine = new TemplateEngine(templatesDir);
    expect(engine.renderPage({ title: 'T', tags: [], body: 'x' }, 'post')).toContain('class="post"');
    expect(engine.renderPage({ title: 'T', tags: [], body: 'x' })).toContain('class="default"');
  });

  it('throws a clear error when a named template has no matching layout file', () => {
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '{{{body}}}');
    const engine = new TemplateEngine(templatesDir);
    expect(() => engine.renderPage({ title: 'T', tags: [], body: 'x' }, 'missing')).toThrow(/Unknown template "missing"/);
  });

  it('resolves and renders partials referenced from a layout', () => {
    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), '<header>Site Header</header>');
    fs.writeFileSync(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>Site Footer</footer>');
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '{{> header}}<main>{{{body}}}</main>{{> footer}}'
    );
    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage({ title: 'T', tags: [], body: 'content' });
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('content');
  });

  it('escapes HTML in title but not in the raw body', () => {
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<h1>{{title}}</h1>{{{body}}}');
    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderPage({ title: '<script>x</script>', tags: [], body: '<p>raw</p>' });
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('<p>raw</p>');
  });

  it('renders the index template with the list of pages', () => {
    fs.writeFileSync(
      path.join(templatesDir, 'index.hbs'),
      '<ul>{{#each pages}}<li><a href="{{outputPath}}">{{title}}</a></li>{{/each}}</ul>'
    );
    const engine = new TemplateEngine(templatesDir);
    const html = engine.renderIndex([makeSamplePage({ title: 'One', outputPath: 'one.html' })]);
    expect(html).toContain('<a href="one.html">One</a>');
  });

  it('falls back to a built-in default layout and index template when the templates directory is missing entirely', () => {
    const missingDir = path.join(templatesDir, 'does-not-exist');
    const engine = new TemplateEngine(missingDir);
    const pageHtml = engine.renderPage({ title: 'Fallback', tags: ['x'], body: '<p>hi</p>' });
    expect(pageHtml).toContain('<h1>Fallback</h1>');
    expect(pageHtml).toContain('<p>hi</p>');

    const indexHtml = engine.renderIndex([makeSamplePage()]);
    expect(indexHtml).toContain('All Pages');
    expect(indexHtml).toContain('href="sample.html"');
  });

  it('still throws for an unknown named template even when falling back for the default', () => {
    const missingDir = path.join(templatesDir, 'does-not-exist');
    const engine = new TemplateEngine(missingDir);
    expect(() => engine.renderPage({ title: 'T', tags: [], body: 'x' }, 'special')).toThrow(/Unknown template "special"/);
  });

  it('caches engines per templates directory via getTemplateEngine', () => {
    const engineA = getTemplateEngine(templatesDir);
    const engineB = getTemplateEngine(templatesDir);
    expect(engineA).toBe(engineB);
  });
});
