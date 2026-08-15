import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { TemplateEngine, DEFAULT_LAYOUT_NAME } from '../src/templates';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

describe('TemplateEngine', () => {
  let templatesDir: string;

  beforeEach(() => {
    templatesDir = makeTempDir('ssg-templates-');

    writeFile(
      path.join(templatesDir, 'partials', 'header.hbs'),
      '<h1>{{title}}</h1>'
    );
    writeFile(
      path.join(templatesDir, 'partials', 'footer.hbs'),
      '<footer>{{> nav}}bye</footer>'
    );
    writeFile(
      path.join(templatesDir, 'partials', 'nav.hbs'),
      '<nav>nav-link</nav>'
    );

    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{> nav}}{{> header}}{{#if date}}<p class="date">{{date}}</p>{{/if}}{{#if tags.length}}{{#each tags}}<span class="tag">{{this}}</span>{{/each}}{{/if}}{{{body}}}{{> footer}}</body></html>'
    );
    writeFile(
      path.join(templatesDir, 'layouts', 'post.hbs'),
      '<html class="post"><body>{{{body}}}</body></html>'
    );
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('throws if the templates directory does not exist', () => {
    expect(() => new TemplateEngine(path.join(templatesDir, 'missing'))).toThrow();
  });

  it('throws if there is no default layout', () => {
    const dir = makeTempDir('ssg-templates-nodefault-');
    writeFile(path.join(dir, 'layouts', 'other.hbs'), '<html>{{{body}}}</html>');

    expect(() => new TemplateEngine(dir)).toThrow(/default/i);
  });

  it('renders the default layout when no layout name is given, injecting body unescaped', () => {
    const engine = new TemplateEngine(templatesDir);

    const html = engine.render(undefined, {
      title: 'My Post',
      date: '2024-01-01',
      tags: ['a', 'b'],
      body: '<p>Body <strong>content</strong></p>',
    });

    expect(html).toContain('<title>My Post</title>');
    expect(html).toContain('<h1>My Post</h1>');
    expect(html).toContain('2024-01-01');
    expect(html).toContain('<span class="tag">a</span>');
    expect(html).toContain('<span class="tag">b</span>');
    expect(html).toContain('<p>Body <strong>content</strong></p>');
  });

  it('includes registered partials, including a partial referencing another partial', () => {
    const engine = new TemplateEngine(templatesDir);
    const html = engine.render(undefined, { title: 'T', tags: [], body: '' });

    expect(html).toContain('nav-link');
    expect(html).toContain('bye');
  });

  it('escapes double-stashed values but not the triple-stashed body', () => {
    const engine = new TemplateEngine(templatesDir);
    const html = engine.render(undefined, {
      title: '<script>alert(1)</script>',
      tags: [],
      body: '<p>raw &amp; safe</p>',
    });

    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('<p>raw &amp; safe</p>');
  });

  it('selects a named layout when one is given', () => {
    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('post', { title: 'T', tags: [], body: '<p>hi</p>' });

    expect(html).toContain('class="post"');
    expect(html).toContain('<p>hi</p>');
  });

  it('throws a clear error when the requested layout does not exist', () => {
    const engine = new TemplateEngine(templatesDir);
    expect(() => engine.render('does-not-exist', { title: 'T', tags: [], body: '' })).toThrow(
      /does-not-exist/
    );
  });

  it('reports which layouts are available via hasLayout', () => {
    const engine = new TemplateEngine(templatesDir);
    expect(engine.hasLayout(DEFAULT_LAYOUT_NAME)).toBe(true);
    expect(engine.hasLayout('post')).toBe(true);
    expect(engine.hasLayout('nope')).toBe(false);
  });
});
