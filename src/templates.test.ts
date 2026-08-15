import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { TemplateEngine } from './templates';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
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

  it('renders a template into a layout via the {{{body}}} placeholder', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<h1>{{title}}</h1>');
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', { title: 'Hi' });

    expect(html).toBe('<html><head><title>Hi</title></head><body><h1>Hi</h1></body></html>');
  });

  it('renders an unescaped HTML body inside the layout even when the body contains markup', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<article>{{{html}}}</article>');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<body>{{{body}}}</body>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', { html: '<p>Bold &amp; safe</p>' });

    expect(html).toBe('<body><article><p>Bold &amp; safe</p></article></body>');
  });

  it('resolves a named layout other than "default"', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'BODY');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'minimal.hbs'), '[{{{body}}}]');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'minimal', {});

    expect(html).toBe('[BODY]');
  });

  it('registers partials from templates/partials and makes them usable via {{> name}}', () => {
    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), '<header>HDR</header>');
    fs.writeFileSync(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>FTR</footer>');
    fs.writeFileSync(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>{{> footer}}</nav>');
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '{{> header}}{{{body}}}{{> nav}}{{> footer}}'
    );
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'CONTENT');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', {});

    expect(html).toBe('<header>HDR</header>CONTENT<nav><footer>FTR</footer></nav><footer>FTR</footer>');
  });

  it('falls back to a built-in default layout when no layout file exists on disk', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<p>hello</p>');
    fs.rmSync(path.join(templatesDir, 'layouts'), { recursive: true, force: true });

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', { title: 'Fallback' });

    expect(html).toContain('<title>Fallback</title>');
    expect(html).toContain('<p>hello</p>');
  });

  it('falls back to a built-in default template when the requested template file is missing', () => {
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '{{{body}}}');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('does-not-exist', 'default', {
      title: 'Untitled',
      html: '<p>content</p>',
      tags: [],
    });

    expect(html).toContain('<h1>Untitled</h1>');
    expect(html).toContain('<p>content</p>');
  });
});
