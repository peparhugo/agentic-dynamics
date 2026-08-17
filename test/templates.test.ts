import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/build';
import { parseFrontmatter } from '../src/ssg';
import { TemplateEngine, renderPage, renderIndex } from '../src/template-engine';
import { Page } from '../src/ssg';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'hello',
    title: 'Hello',
    tags: [],
    html: '<p>Hello body</p>',
    frontmatter: {},
    ...overrides,
  };
}

describe('parseFrontmatter template fields', () => {
  it('reads template and layout from frontmatter', () => {
    const raw = `---
title: T
template: fancy
layout: wide
---
body`;
    const { frontmatter } = parseFrontmatter(raw);
    expect(frontmatter.template).toBe('fancy');
    expect(frontmatter.layout).toBe('wide');
  });

  it('defaults template and layout to undefined when omitted', () => {
    const { frontmatter } = parseFrontmatter('---\ntitle: T\n---\nbody');
    expect(frontmatter.template).toBeUndefined();
    expect(frontmatter.layout).toBeUndefined();
  });
});

describe('TemplateEngine', () => {
  it('renders a page with a template selected from frontmatter', () => {
    const templatesDir = makeTempDir();
    writeFile(
      path.join(templatesDir, 'special.hbs'),
      '<div class="special">{{title}}</div>\n{{{content}}}\n'
    );

    const engine = new TemplateEngine({ templatesDir });
    const html = engine.renderPage(makePage({ template: 'special', title: 'Special' }));

    expect(html).toContain('<div class="special">Special</div>');
    expect(html).toContain('<p>Hello body</p>');
  });

  it('renders a page wrapped in a layout using the {{{body}}} placeholder', () => {
    const templatesDir = makeTempDir();
    writeFile(
      path.join(templatesDir, 'layouts', 'wide.hbs'),
      '<html><head><title>{{title}}</title></head><body><main>{{{body}}}</main></body></html>'
    );

    const engine = new TemplateEngine({ templatesDir });
    const html = engine.renderPage(makePage({ layout: 'wide', title: 'Wide' }));

    expect(html).toContain('<title>Wide</title>');
    expect(html).toContain('<main>');
    expect(html).toContain('<p>Hello body</p>');
  });

  it('applies partials (header, nav, footer) from the partials directory', () => {
    const templatesDir = makeTempDir();
    writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>Site Header</header>');
    writeFile(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>Menu</nav>');
    writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>Site Footer</footer>');
    writeFile(
      path.join(templatesDir, 'layouts', 'main.hbs'),
      '<html><body>{{> header}}{{> nav}}<main>{{{body}}}</main>{{> footer}}</body></html>'
    );

    const engine = new TemplateEngine({ templatesDir });
    const html = engine.renderPage(makePage({ layout: 'main' }));

    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<nav>Menu</nav>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<p>Hello body</p>');
  });

  it('escapes handlebars variables but leaves triple-stache content raw', () => {
    const engine = new TemplateEngine({ templatesDir: makeTempDir() });
    const page = makePage({
      title: '<b>Title</b> & "quoted"',
      html: '<strong>bold</strong>',
    });

    const html = engine.renderPage(page);

    expect(html).toContain('&lt;b&gt;Title&lt;/b&gt;');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('exposes custom frontmatter fields to templates', () => {
    const templatesDir = makeTempDir();
    writeFile(
      path.join(templatesDir, 'about.hbs'),
      '<h1>{{title}}</h1><p>{{author}}</p>\n{{{content}}}\n'
    );

    const engine = new TemplateEngine({ templatesDir });
    const html = engine.renderPage(
      makePage({ template: 'about', title: 'About', frontmatter: { author: 'Jane' } })
    );

    expect(html).toContain('<p>Jane</p>');
  });

  it('uses an overridden index template', () => {
    const templatesDir = makeTempDir();
    writeFile(
      path.join(templatesDir, 'index.hbs'),
      '<ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
    );

    const engine = new TemplateEngine({ templatesDir });
    const html = engine.renderIndex([makePage({ title: 'A' }), makePage({ slug: 'b', title: 'B' })]);

    expect(html).toContain('<li>A</li>');
    expect(html).toContain('<li>B</li>');
  });

  it('throws when an explicitly requested template is missing', () => {
    const engine = new TemplateEngine({ templatesDir: makeTempDir() });
    expect(() => engine.renderPage(makePage({ template: 'nope' }))).toThrow(/Template not found/);
  });

  it('throws when an explicitly requested layout is missing', () => {
    const engine = new TemplateEngine({ templatesDir: makeTempDir() });
    expect(() => engine.renderPage(makePage({ layout: 'nope' }))).toThrow(/Template not found/);
  });

  it('falls back to built-in defaults when no templates directory exists', () => {
    const engine = new TemplateEngine({ templatesDir: path.join(makeTempDir(), 'missing') });
    const html = engine.renderPage(makePage({ title: 'Default', date: '2024-01-01' }));

    expect(html).toContain('<h1>Default</h1>');
    expect(html).toContain('2024-01-01');
    expect(html).toContain('<p>Hello body</p>');
  });
});

describe('standalone render helpers', () => {
  it('renderPage and renderIndex work without a templates directory', () => {
    const html = renderPage(makePage({ title: 'Standalone' }));
    expect(html).toContain('<h1>Standalone</h1>');

    const index = renderIndex([makePage({ title: 'Standalone' })]);
    expect(index).toContain('Standalone');
  });
});

describe('build with templates', () => {
  it('renders pages using layout, template and partials from the templates directory', () => {
    const contentDir = makeTempDir();
    const templatesDir = makeTempDir();
    const outputDir = makeTempDir();

    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body>{{> header}}<main>{{{body}}}</main>{{> footer}}</body></html>'
    );
    writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>My Blog</header>');
    writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>Goodbye</footer>');
    writeFile(
      path.join(templatesDir, 'post.hbs'),
      '<article><h1>{{title}}</h1>{{{content}}}</article>'
    );

    writeFile(
      path.join(contentDir, 'welcome.md'),
      `---
title: Welcome
template: post
---
# Hi

Welcome body.
`
    );

    const result = build({ contentDir, outputDir, templatesDir });

    expect(result.writtenFiles).toHaveLength(2);

    const pageHtml = fs.readFileSync(path.join(outputDir, 'welcome.html'), 'utf8');
    expect(pageHtml).toContain('<header>My Blog</header>');
    expect(pageHtml).toContain('<footer>Goodbye</footer>');
    expect(pageHtml).toContain('<article><h1>Welcome</h1>');
    expect(pageHtml).toContain('<h1>Hi</h1>');
    expect(pageHtml).toContain('<main>');
  });

  it('renders pages without frontmatter template using the default template file', () => {
    const contentDir = makeTempDir();
    const templatesDir = makeTempDir();
    const outputDir = makeTempDir();

    writeFile(path.join(templatesDir, 'page.hbs'), '<div class="default">{{title}}</div>{{{content}}}');
    writeFile(
      path.join(contentDir, 'plain.md'),
      `---
title: Plain
---
Body
`
    );

    build({ contentDir, outputDir, templatesDir });

    const pageHtml = fs.readFileSync(path.join(outputDir, 'plain.html'), 'utf8');
    expect(pageHtml).toContain('<div class="default">Plain</div>');
  });
});
