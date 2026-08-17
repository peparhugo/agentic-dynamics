import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/builder';
import { TemplateEngine } from '../src/templates';

function tmpdir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

function writeFile(root: string, rel: string, contents: string): string {
  const full = path.join(root, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, contents);
  return full;
}

describe('templates', () => {
  it('renders a page with a custom template specified in frontmatter', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Hello\ntemplate: post\n---\nBody *text*\n');
    writeFile(
      templates,
      'post.hbs',
      '<article class="post"><h1>{{title}}</h1>{{{content}}}</article>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<article class="post">');
    expect(page).toContain('<h1>Hello</h1>');
    expect(page).toContain('<em>text</em>');
    expect(page).toContain('<html');
  });

  it('renders a page with a custom layout using the {{{body}}} placeholder', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Wide\nlayout: wide\n---\nBody\n');
    writeFile(
      templates,
      'layouts/wide.hbs',
      '<html><body><div class="wide">{{{body}}}</div></body></html>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<div class="wide">');
    expect(page).toContain('<article>');
    expect(page).toContain('<h1>Wide</h1>');
    expect(page).toContain('<p>Body</p>');
  });

  it('includes header, footer and nav partials', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Partials\nlayout: main\n---\nBody\n');
    writeFile(templates, 'partials/header.hbs', '<header id="site-header">Site</header>\n');
    writeFile(templates, 'partials/footer.hbs', '<footer id="site-footer">Footer</footer>\n');
    writeFile(templates, 'partials/nav.hbs', '<nav id="site-nav">Nav</nav>\n');
    writeFile(
      templates,
      'layouts/main.hbs',
      '<html><body>{{> header}}{{> nav}}{{{body}}}{{> footer}}</body></html>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<header id="site-header">Site</header>');
    expect(page).toContain('<footer id="site-footer">Footer</footer>');
    expect(page).toContain('<nav id="site-nav">Nav</nav>');
    expect(page).toContain('<h1>Partials</h1>');
  });

  it('uses a default template override when none is specified', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Default\n---\nBody\n');
    writeFile(templates, 'default.hbs', '<main>{{{content}}}</main>\n');

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toMatch(/<main>\s*<p>Body<\/p>\s*<\/main>/);
  });

  it('exposes custom frontmatter values to the template', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(
      content,
      'post.md',
      '---\ntitle: Note\nkind: note\ntemplate: post\n---\nBody\n'
    );
    writeFile(
      templates,
      'post.hbs',
      '<h1>{{title}}</h1><p class="{{kind}}">{{{content}}}</p>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<p class="note">');
  });

  it('escapes frontmatter values rendered with double-stash', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(
      content,
      'post.md',
      '---\ntitle: <script>alert(1)</script>\ntemplate: post\n---\nBody\n'
    );
    writeFile(templates, 'post.hbs', '<h1>{{title}}</h1>{{{content}}}\n');

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('&lt;script&gt;');
    expect(page).not.toContain('<script>alert(1)</script>');
  });

  it('resolves template and layout names that already carry the .hbs extension', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(
      content,
      'post.md',
      '---\ntitle: Ext\ntemplate: post.hbs\nlayout: wide.hbs\n---\nBody\n'
    );
    writeFile(templates, 'post.hbs', '<section>{{{content}}}</section>\n');
    writeFile(
      templates,
      'layouts/wide.hbs',
      '<html><body>{{{body}}}</body></html>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toMatch(/<section>\s*<p>Body<\/p>\s*<\/section>/);
    expect(page).toContain('<html><body>');
  });

  it('supports nested partial names from subdirectories', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Nested\nlayout: main\n---\nBody\n');
    writeFile(templates, 'partials/nav/main.hbs', '<nav id="nav-main">Nav</nav>\n');
    writeFile(
      templates,
      'layouts/main.hbs',
      '<html><body>{{> nav/main}}{{{body}}}</body></html>\n'
    );

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<nav id="nav-main">Nav</nav>');
  });

  it('throws when a named template does not exist', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Missing\ntemplate: nope\n---\nBody\n');

    expect(() =>
      build({ contentDir: content, outputDir: output, templatesDir: templates })
    ).toThrow(/Template not found: nope/);
  });

  it('throws when a named layout does not exist', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'templates');
    writeFile(content, 'post.md', '---\ntitle: Missing\nlayout: nope\n---\nBody\n');

    expect(() =>
      build({ contentDir: content, outputDir: output, templatesDir: templates })
    ).toThrow(/Layout not found: nope/);
  });

  it('still produces full HTML when no templates directory exists', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const templates = path.join(root, 'does-not-exist');
    writeFile(content, 'post.md', '---\ntitle: Plain\n---\nBody\n');

    build({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<html');
    expect(page).toContain('<title>Plain</title>');
    expect(page).toContain('<h1>Plain</h1>');
  });

  it('renders the built-in default template and layout', () => {
    const engine = new TemplateEngine('/nonexistent');
    const html = engine.render(null, null, {
      title: 'Hi',
      date: '2024-01-01',
      tags: ['a'],
      content: '<p>hello</p>',
      home: 'index.html',
      meta: '<time datetime="2024-01-01">2024-01-01</time>',
    });
    expect(html).toContain('<title>Hi</title>');
    expect(html).toContain('<h1>Hi</h1>');
    expect(html).toContain('<div class="content">');
    expect(html).toContain('<p>hello</p>');
    expect(html).toContain('<header><a href="index.html">Home</a></header>');
  });
});
