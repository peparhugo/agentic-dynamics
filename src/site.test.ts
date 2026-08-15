import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { buildSite } from './site';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-content-');
    outputDir = makeTmpDir('ssg-output-');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('generates an HTML file per markdown page', () => {
    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      '---\ntitle: Hello\ndate: 2026-01-01\ntags: [a, b]\n---\n\n# Hi there\n'
    );
    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      '---\ntitle: Second Page\n---\n\nSome content.\n'
    );

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);

    const helloHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(helloHtml).toContain('<h1>Hello</h1>');
    expect(helloHtml).toContain('Hi there');
    expect(helloHtml).toContain('a');
    expect(helloHtml).toContain('b');
  });

  it('generates an index.html listing all pages', () => {
    fs.writeFileSync(path.join(contentDir, 'one.md'), '---\ntitle: One\n---\nBody one.');
    fs.writeFileSync(path.join(contentDir, 'two.md'), '---\ntitle: Two\n---\nBody two.');

    buildSite({ contentDir, outputDir });

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexHtml = fs.readFileSync(indexPath, 'utf-8');
    expect(indexHtml).toContain('One');
    expect(indexHtml).toContain('Two');
    expect(indexHtml).toContain('href="one.html"');
    expect(indexHtml).toContain('href="two.html"');
  });

  it('falls back to a title derived from the filename when frontmatter has none', () => {
    fs.writeFileSync(path.join(contentDir, 'my-cool-post.md'), 'No frontmatter here.');

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages[0].title).toBe('My Cool Post');
  });

  it('supports nested content directories', () => {
    fs.mkdirSync(path.join(contentDir, 'posts'));
    fs.writeFileSync(
      path.join(contentDir, 'posts', 'nested.md'),
      '---\ntitle: Nested Post\n---\nNested body.'
    );

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages[0].outputPath).toBe('posts/nested.html');
    expect(fs.existsSync(path.join(outputDir, 'posts', 'nested.html'))).toBe(true);
  });

  it('throws a clear error when the content directory does not exist', () => {
    const missingDir = path.join(contentDir, 'does-not-exist');
    expect(() => buildSite({ contentDir: missingDir, outputDir })).toThrow(/not found/i);
  });
});

describe('buildSite with a custom templates directory', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-tpl-content-');
    outputDir = makeTmpDir('ssg-tpl-output-');
    templatesDir = makeTmpDir('ssg-tpl-templates-');
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.mkdirSync(path.join(templatesDir, 'partials'));
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('uses the default template and layout when a page specifies neither', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<h1>{{title}}</h1><div>{{{html}}}</div>');
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><title>{{title}}</title><body>{{{body}}}</body></html>'
    );
    fs.writeFileSync(path.join(contentDir, 'plain.md'), '---\ntitle: Plain\n---\n\nBody text.');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'plain.html'), 'utf-8');
    expect(html).toContain('<html><title>Plain</title><body><h1>Plain</h1><div>');
    expect(html).toContain('<p>Body text.</p>');
    expect(html).toContain('</div></body></html>');
  });

  it('lets a page pick a non-default template via frontmatter', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'DEFAULT:{{title}}');
    fs.writeFileSync(path.join(templatesDir, 'post.hbs'), 'POST:{{title}}');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '{{{body}}}');
    fs.writeFileSync(
      path.join(contentDir, 'article.md'),
      '---\ntitle: Article\ntemplate: post\n---\n\nSome text.'
    );

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'article.html'), 'utf-8');
    expect(html).toBe('POST:Article');
  });

  it('lets a page pick a non-default layout via frontmatter', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'CONTENT');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), 'DEFAULT[{{{body}}}]');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'bare.hbs'), 'BARE[{{{body}}}]');
    fs.writeFileSync(
      path.join(contentDir, 'note.md'),
      '---\ntitle: Note\nlayout: bare\n---\n\nText.'
    );

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'note.html'), 'utf-8');
    expect(html).toBe('BARE[CONTENT]');
  });

  it('renders header/footer/nav partials referenced from the layout', () => {
    fs.writeFileSync(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>NAV</nav>');
    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{> nav}}</header>');
    fs.writeFileSync(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>FOOTER</footer>');
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '{{> header}}{{{body}}}{{> footer}}'
    );
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE');
    fs.writeFileSync(path.join(contentDir, 'p.md'), '---\ntitle: P\n---\n\nText.');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'p.html'), 'utf-8');
    expect(html).toBe('<header><nav>NAV</nav></header>PAGE<footer>FOOTER</footer>');
  });

  it('renders the generated index through the index template and default layout', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '{{title}}');
    fs.writeFileSync(path.join(templatesDir, 'index.hbs'), 'INDEX:{{#each pages}}{{title}};{{/each}}');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '[{{title}}]{{{body}}}');
    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\n\nText.');
    fs.writeFileSync(path.join(contentDir, 'b.md'), '---\ntitle: B\n---\n\nText.');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(html).toBe('[Index]INDEX:A;B;');
  });

  it('falls back to a built-in default template/layout when no matching files exist on disk', () => {
    fs.writeFileSync(path.join(contentDir, 'fallback.md'), '---\ntitle: Fallback Page\n---\n\nHello.');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'fallback.html'), 'utf-8');
    expect(html).toContain('<title>Fallback Page</title>');
    expect(html).toContain('<h1>Fallback Page</h1>');
    expect(html).toContain('Hello.');
  });
});
