import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from './index';
import { TemplateEngine, DEFAULT_LAYOUT_SOURCE } from './templates';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

function write(file: string, content: string): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
}

describe('template engine', () => {
  it('wraps page content with a layout via the {{{body}}} placeholder', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(path.join(content, 'post.md'), '---\ntitle: My Post\n---\nHello **world**\n');
    write(
      path.join(templates, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(html).toContain('<title>My Post</title>');
    expect(html).toContain('Hello <strong>world</strong>');
  });

  it('uses a template specified in frontmatter', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(
      path.join(content, 'post.md'),
      '---\ntitle: Post\ntemplate: post\n---\nBody\n'
    );
    write(
      path.join(templates, 'post.hbs'),
      '<article class="post"><h1>{{title}}</h1>{{{body}}}</article>'
    );

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(html).toContain('<article class="post">');
    expect(html).toContain('<h1>Post</h1>');
    expect(html).toContain('Body');
    expect(html).toContain('<div class="content">');
  });

  it('uses a layout specified in frontmatter', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(
      path.join(content, 'post.md'),
      '---\ntitle: Post\nlayout: blank\n---\nBody\n'
    );
    write(path.join(templates, 'layouts', 'blank.hbs'), '{{{body}}}');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(html).toContain('Body');
    expect(html).not.toContain('<div class="content">');
    expect(html).not.toContain('<!DOCTYPE html>');
  });

  it('supports partials (header, footer, nav)', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(path.join(content, 'a.md'), '---\ntitle: A\n---\nAlpha\n');
    write(path.join(content, 'b.md'), '---\ntitle: B\n---\nBeta\n');
    write(path.join(templates, 'partials', 'header.hbs'), '<header>Site Header</header>');
    write(path.join(templates, 'partials', 'footer.hbs'), '<footer>Site Footer</footer>');
    write(
      path.join(templates, 'partials', 'nav.hbs'),
      '<nav>{{#each site.pages}}<a href="{{url}}">{{title}}</a>{{/each}}</nav>'
    );
    write(
      path.join(templates, 'layouts', 'default.hbs'),
      '<html><body>{{> header}}{{> nav}}{{{body}}}{{> footer}}</body></html>'
    );

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'a.html'), 'utf8');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<nav>');
    expect(html).toContain('href="a.html"');
    expect(html).toContain('href="b.html"');
  });

  it('uses the default template file when no template is specified', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(path.join(content, 'post.md'), '---\ntitle: Post\n---\nBody\n');
    write(path.join(templates, 'default.hbs'), '<div class="wrapped">{{{body}}}</div>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(html).toContain('<div class="wrapped">');
    expect(html).toContain('Body');
  });

  it('skips the layout when layout: false is set', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(path.join(content, 'post.md'), '---\ntitle: Post\nlayout: false\n---\nBody\n');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(html).toContain('Body');
    expect(html).not.toContain('<!DOCTYPE html>');
    expect(html).not.toContain('<div class="content">');
  });

  it('exposes custom frontmatter fields to templates', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();

    write(
      path.join(content, 'post.md'),
      '---\ntitle: Post\nauthor: Jane\ntemplate: byline\n---\nBody\n'
    );
    write(
      path.join(templates, 'byline.hbs'),
      '<p class="author">{{author}}</p>{{{body}}}'
    );

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(html).toContain('<p class="author">Jane</p>');
  });
});

describe('TemplateEngine', () => {
  it('falls back to the built-in layout when no layout file exists', () => {
    const templates = makeTempDir();
    const engine = new TemplateEngine(templates);
    const html = engine.render(undefined, undefined, {
      title: 'Fallback',
      content: '<p>hi</p>',
    });
    expect(html).toContain('<title>Fallback</title>');
    expect(html).toContain('<p>hi</p>');
    expect(html).toContain('<div class="content">');
  });

  it('renders raw HTML through triple-stache but escapes double-stache', () => {
    const templates = makeTempDir();
    write(
      path.join(templates, 'layouts', 'default.hbs'),
      '<h1>{{title}}</h1><div>{{{body}}}</div>'
    );
    const engine = new TemplateEngine(templates);
    const html = engine.render(undefined, undefined, {
      title: '<script>',
      content: '<strong>bold</strong>',
    });
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('exports the default layout source', () => {
    expect(DEFAULT_LAYOUT_SOURCE).toContain('{{{body}}}');
  });
});
