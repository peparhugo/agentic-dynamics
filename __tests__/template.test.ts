import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, renderIndex, renderPage } from '../src/site';
import { TemplateEngine, DEFAULT_TEMPLATES_DIR, DEFAULT_TEMPLATE, DEFAULT_LAYOUT } from '../src/template';
import { parseMarkdown } from '../src/markdown';
import { Page } from '../src/types';

interface TempDir {
  dir: string;
  cleanup: () => void;
}

function makeTempDir(): TempDir {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
  return { dir, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

function writeFile(dir: string, relPath: string, content: string): void {
  const full = path.join(dir, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content, 'utf8');
}

function writeTemplates(dir: string): void {
  writeFile(dir, 'templates/default.hbs', '<article>DEFAULT TEMPLATE: {{title}}\n{{{html}}}</article>');
  writeFile(dir, 'templates/post.hbs', '<article>POST TEMPLATE: {{title}}</article>');
  writeFile(
    dir,
    'templates/layouts/default.hbs',
    '<html><head><title>{{title}}</title></head><body>{{> header}}{{{body}}}{{> footer}}</body></html>'
  );
  writeFile(dir, 'templates/partials/header.hbs', '<header>HEADER</header>');
  writeFile(dir, 'templates/partials/footer.hbs', '<footer>FOOTER</footer>');
  writeFile(dir, 'templates/partials/nav.hbs', '<nav>NAV</nav>');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    title: 'Test Page',
    slug: 'test-page',
    tags: [],
    body: '',
    html: '<p>Body</p>',
    excerpt: 'Body',
    filePath: 'test-page.md',
    ...overrides,
  };
}

describe('parseMarkdown template frontmatter', () => {
  it('reads template and layout from frontmatter', () => {
    const page = parseMarkdown(
      ['---', 'title: X', 'template: post', 'layout: wide', '---', 'Body'].join('\n'),
      'x.md'
    );
    expect(page.template).toBe('post');
    expect(page.layout).toBe('wide');
  });

  it('leaves template undefined when not specified', () => {
    const page = parseMarkdown('# Only heading', 'x.md');
    expect(page.template).toBeUndefined();
    expect(page.layout).toBeUndefined();
  });
});

describe('TemplateEngine', () => {
  it('exposes default template and layout names', () => {
    expect(DEFAULT_TEMPLATE).toBe('default');
    expect(DEFAULT_LAYOUT).toBe('default');
  });

  it('loads templates, layouts, and partials from a directory', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    expect(engine.hasTemplate('post')).toBe(true);
    expect(engine.hasTemplate('default')).toBe(true);
    expect(engine.hasLayout('default')).toBe(true);

    const page = makePage({ template: 'post' });
    const html = renderPage(page, engine);
    expect(html).toContain('POST TEMPLATE: Test Page');
    expect(html).toContain('HEADER');
    expect(html).toContain('FOOTER');
    cleanup();
  });
});

describe('renderPage with templates', () => {
  it('uses the template named in frontmatter', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage({ template: 'post' }), engine);
    expect(html).toContain('POST TEMPLATE: Test Page');
    expect(html).not.toContain('DEFAULT TEMPLATE');
    cleanup();
  });

  it('uses the default template when none is specified', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage(), engine);
    expect(html).toContain('DEFAULT TEMPLATE: Test Page');
    cleanup();
  });

  it('wraps page content in a layout with the {{{body}}} placeholder', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage({ html: '<p>Inner</p>' }), engine);
    expect(html).toContain('<p>Inner</p>');
    expect(html).toContain('DEFAULT TEMPLATE: Test Page');
    expect(html).toContain('<html><head>');
    cleanup();
  });

  it('renders partials from the partials directory', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage(), engine);
    expect(html).toContain('<header>HEADER</header>');
    expect(html).toContain('<footer>FOOTER</footer>');
    cleanup();
  });

  it('uses the default layout when layout is not specified', () => {
    const { dir, cleanup } = makeTempDir();
    writeFile(dir, 'templates/page.hbs', '<p>{{title}}</p>');
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage({ template: 'page' }), engine);
    expect(html).toContain('<p>Test Page</p>');
    expect(html).toContain('<html lang="en">');
    cleanup();
  });

  it('skips the layout when layout is "none"', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage({ template: 'post', layout: 'none' }), engine);
    expect(html).toContain('POST TEMPLATE: Test Page');
    expect(html).not.toContain('<html><head>');
    cleanup();
  });

  it('throws when the specified template is missing', () => {
    const { dir, cleanup } = makeTempDir();
    writeTemplates(dir);
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    expect(() => renderPage(makePage({ template: 'missing' }), engine)).toThrow(
      /template not found: missing/
    );
    cleanup();
  });

  it('makes page data available to templates and escapes values', () => {
    const { dir, cleanup } = makeTempDir();
    writeFile(dir, 'templates/simple.hbs', '<h1>{{title}}</h1><div>{{{html}}}</div>');
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(
      makePage({ title: 'A <Post>', template: 'simple' }),
      engine
    );
    expect(html).toContain('A &lt;Post&gt;');
    expect(html).toContain('<p>Body</p>');
    cleanup();
  });
});

describe('EJS templates', () => {
  it('renders EJS page templates, layouts, and includes', () => {
    const { dir, cleanup } = makeTempDir();
    writeFile(dir, 'templates/ejs.hbs', 'ignored');
    writeFile(
      dir,
      'templates/post.ejs',
      '<article><h1><%= title %></h1><div><%- html %></div><ul><% for (const t of tags) { %><li><%= t %></li><% } %></ul></article>'
    );
    writeFile(
      dir,
      'templates/layouts/default.ejs',
      '<html><body><%- include("header") %><%- body %></body></html>'
    );
    writeFile(dir, 'templates/partials/header.ejs', '<header>EJS HEADER</header>');

    const engine = new TemplateEngine(path.join(dir, 'templates'));
    const page = makePage({
      template: 'post',
      tags: ['a', 'b'],
      html: '<p>Raw</p>',
    });
    const html = renderPage(page, engine);

    expect(html).toContain('<h1>Test Page</h1>');
    expect(html).toContain('<p>Raw</p>');
    expect(html).toContain('<li>a</li>');
    expect(html).toContain('<li>b</li>');
    expect(html).toContain('EJS HEADER');
    cleanup();
  });

  it('escapes <%= output but not <%- output', () => {
    const { dir, cleanup } = makeTempDir();
    writeFile(dir, 'templates/t.ejs', '<p><%= title %></p><p><%- title %></p>');
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const html = renderPage(makePage({ template: 't', title: 'A <B>' }), engine);
    expect(html).toContain('A &lt;B&gt;');
    expect(html).toContain('A <B>');
    cleanup();
  });
});

describe('renderIndex with templates', () => {
  it('uses an index template when provided', () => {
    const { dir, cleanup } = makeTempDir();
    writeFile(
      dir,
      'templates/index.hbs',
      '<main><h1>Home</h1>{{#each pages}}<a href="{{slug}}.html">{{title}}</a>{{/each}}</main>'
    );
    const engine = new TemplateEngine(path.join(dir, 'templates'));

    const pages = [
      makePage({ title: 'One', slug: 'one' }),
      makePage({ title: 'Two', slug: 'two' }),
    ];
    const html = renderIndex(pages, engine);
    expect(html).toContain('<h1>Home</h1>');
    expect(html).toContain('one.html');
    expect(html).toContain('two.html');
    cleanup();
  });
});

describe('buildSite with templates', () => {
  it('uses the template engine when a templates directory is provided', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    const templatesDir = path.join(dir, 'templates');

    writeFile(contentDir, 'hello.md', '---\ntitle: Hello\n---\nHi there.');
    writeTemplates(dir);

    const result = buildSite(contentDir, outDir, templatesDir);
    expect(result.pages).toBe(1);

    const page = fs.readFileSync(path.join(outDir, 'hello.html'), 'utf8');
    expect(page).toContain('DEFAULT TEMPLATE: Hello');
    expect(page).toContain('HEADER');
    expect(page).toContain('FOOTER');
    expect(page).toContain('<p>Hi there.</p>');
    cleanup();
  });

  it('uses built-in defaults when no templates directory exists', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');

    writeFile(contentDir, 'hello.md', '---\ntitle: Hello\n---\nHi.');
    const result = buildSite(contentDir, outDir, path.join(dir, 'templates'));
    expect(result.pages).toBe(1);

    const page = fs.readFileSync(path.join(outDir, 'hello.html'), 'utf8');
    expect(page).toContain('<h1>Hello</h1>');
    expect(page).toContain('<p>Hi.</p>');
    cleanup();
  });
});
