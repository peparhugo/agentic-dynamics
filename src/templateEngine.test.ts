import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { TemplateEngine } from './templateEngine';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf-8');
}

describe('TemplateEngine', () => {
  let templatesDir: string;

  beforeEach(() => {
    templatesDir = makeTempDir('ssg-templates-');
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('renders a template and wraps it in a layout via the {{{body}}} placeholder', () => {
    writeFile(path.join(templatesDir, 'page.hbs'), '<p>{{{content}}}</p>');
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', { content: 'Hello' }, {});

    expect(html).toBe('<html><body><p>Hello</p></body></html>');
  });

  it('supports partials/includes referenced from a layout', () => {
    writeFile(path.join(templatesDir, 'page.hbs'), '{{{content}}}');
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '{{> header}}{{{body}}}{{> footer}}');
    writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{{siteTitle}}}</header>');
    writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>done</footer>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', { content: 'Body' }, { siteTitle: 'My Site' });

    expect(html).toBe('<header>My Site</header>Body<footer>done</footer>');
  });

  it('supports a partial that includes another partial (nested includes)', () => {
    writeFile(path.join(templatesDir, 'page.hbs'), '{{{content}}}');
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '{{> header}}{{{body}}}');
    writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{> nav}}</header>');
    writeFile(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>links</nav>');

    const engine = new TemplateEngine(templatesDir);
    const html = engine.render('page', 'default', { content: 'Body' }, {});

    expect(html).toBe('<header><nav>links</nav></header>Body');
  });

  it('lets different pages select different templates and layouts', () => {
    writeFile(path.join(templatesDir, 'page.hbs'), '<article>{{{content}}}</article>');
    writeFile(path.join(templatesDir, 'post.hbs'), '<post>{{{content}}}</post>');
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '[default]{{{body}}}');
    writeFile(path.join(templatesDir, 'layouts', 'wide.hbs'), '[wide]{{{body}}}');

    const engine = new TemplateEngine(templatesDir);

    expect(engine.render('page', 'default', { content: 'A' }, {})).toBe('[default]<article>A</article>');
    expect(engine.render('post', 'wide', { content: 'B' }, {})).toBe('[wide]<post>B</post>');
  });

  it('throws a clear error when the requested template is missing', () => {
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '{{{body}}}');
    const engine = new TemplateEngine(templatesDir);
    expect(() => engine.render('missing', 'default', {}, {})).toThrow(/Template not found/);
  });

  it('throws a clear error when the requested layout is missing', () => {
    writeFile(path.join(templatesDir, 'page.hbs'), '{{{content}}}');
    const engine = new TemplateEngine(templatesDir);
    expect(() => engine.render('page', 'missing', {}, {})).toThrow(/Layout not found/);
  });

  it('works when no partials directory is present', () => {
    writeFile(path.join(templatesDir, 'page.hbs'), 'x');
    writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '{{{body}}}');
    const engine = new TemplateEngine(templatesDir);
    expect(engine.render('page', 'default', {}, {})).toBe('x');
  });
});
