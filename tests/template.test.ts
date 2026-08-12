import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { buildSite } from '../src/build';
import { renderPage, renderIndex, pageTitle } from '../src/template';
import { detectEngine, findTemplateFile } from '../src/template-engine';
import type { Page } from '../src/types';

describe('template engine', () => {
  let tmp: string;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
  });

  afterEach(() => {
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  const contentDir = (): string => path.join(tmp, 'content');
  const templatesDir = (): string => path.join(tmp, 'templates');
  const outputDir = (): string => path.join(tmp, 'dist');

  function writeContent(relPath: string, content: string): string {
    const full = path.join(contentDir(), relPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  function writeTemplate(relPath: string, content: string): string {
    const full = path.join(templatesDir(), relPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  function build(opts: { defaultTemplate?: string; defaultLayout?: string } = {}): Promise<Page[]> {
    return buildSite({
      contentDir: contentDir(),
      outputDir: outputDir(),
      siteTitle: 'Templated Site',
      templatesDir: templatesDir(),
      defaultTemplate: opts.defaultTemplate,
      defaultLayout: opts.defaultLayout,
    });
  }

  it('renders a Handlebars template selected via frontmatter', async () => {
    writeTemplate('post.hbs', '<article class="post">\n<h1>{{title}}</h1>\n{{{html}}}\n</article>');
    writeContent('hello.md', '---\ntitle: Hello\ntemplate: post\n---\n\n# Hi there\n\nWelcome!');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'hello.html'), 'utf8');
    expect(html).toContain('<article class="post">');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<h1>Hi there</h1>');
    expect(html).toContain('<p>Welcome!</p>');
    expect(html).toContain('<title>Hello</title>');
  });

  it('uses the default template when none is specified in frontmatter', async () => {
    writeTemplate('default.hbs', '<main class="default-page">\n<h1>{{title}}</h1>\n{{{html}}}\n</main>');
    writeContent('about.md', '---\ntitle: About Us\n---\n\n# About');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'about.html'), 'utf8');
    expect(html).toContain('<main class="default-page">');
    expect(html).toContain('<h1>About Us</h1>');
    expect(html).toContain('<h1>About</h1>');
  });

  it('uses a configured default template name', async () => {
    writeTemplate('custom.hbs', '<div class="custom">{{title}}</div>\n{{{html}}}');
    writeContent('page.md', '# Body');

    await build({ defaultTemplate: 'custom' });

    const html = fs.readFileSync(path.join(outputDir(), 'page.html'), 'utf8');
    expect(html).toContain('<div class="custom">page</div>');
  });

  it('wraps page content in a layout via the {{{body}}} placeholder', async () => {
    writeTemplate('layouts/default.hbs', [
      '<!DOCTYPE html>',
      '<html lang="en">',
      '<head>',
      '<meta charset="utf-8">',
      '<title>{{title}}</title>',
      '</head>',
      '<body>',
      '{{{body}}}',
      '</body>',
      '</html>',
    ].join('\n'));
    writeContent('page.md', '---\ntitle: Wrapped\n---\n\n# Content');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'page.html'), 'utf8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Wrapped</title>');
    expect(html).toContain('<h1>Content</h1>');
    expect(html).toContain('</body>');
    expect(html).toContain('</html>');
  });

  it('supports partials (header, footer, nav) inside templates and layouts', async () => {
    writeTemplate('partials/header.hbs', '<header class="site-header">Header</header>');
    writeTemplate('partials/nav.hbs', '<nav class="site-nav">Home | About</nav>');
    writeTemplate('partials/footer.hbs', '<footer class="site-footer">Footer</footer>');
    writeTemplate('layouts/default.hbs', '<html>\n<body>\n{{> header}}\n{{{body}}}\n{{> footer}}\n</body>\n</html>');
    writeTemplate('post.hbs', '{{> nav}}\n<article>\n<h1>{{title}}</h1>\n{{{html}}}\n</article>');
    writeContent('post.md', '---\ntitle: Partial Post\ntemplate: post\n---\n\n# Post');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'post.html'), 'utf8');
    expect(html).toContain('<header class="site-header">Header</header>');
    expect(html).toContain('<nav class="site-nav">Home | About</nav>');
    expect(html).toContain('<footer class="site-footer">Footer</footer>');
    expect(html).toContain('<h1>Partial Post</h1>');
  });

  it('renders EJS templates with an EJS layout', async () => {
    writeTemplate('layouts/default.ejs', [
      '<!DOCTYPE html>',
      '<html>',
      '<head><title><%= title %></title></head>',
      '<body>',
      '<header>EJS Header</header>',
      '<%- body %>',
      '</body>',
      '</html>',
    ].join('\n'));
    writeTemplate('post.ejs', '<article>\n<h1><%= title %></h1>\n<%- html %>\n</article>');
    writeContent('ejs.md', '---\ntitle: EJS Post\ntemplate: post\n---\n\n# EJS body');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'ejs.html'), 'utf8');
    expect(html).toContain('<title>EJS Post</title>');
    expect(html).toContain('<header>EJS Header</header>');
    expect(html).toContain('<h1>EJS Post</h1>');
    expect(html).toContain('<h1>EJS body</h1>');
  });

  it('renders EJS partials via include()', async () => {
    writeTemplate('partials/banner.ejs', '<div class="banner">EJS Banner</div>');
    writeTemplate('page.ejs', '<%- include(\'banner\') %>\n<h1><%= title %></h1>\n<%- html %>');
    writeContent('ejs.md', '---\ntitle: Banner Page\ntemplate: page\n---\n\n# Body');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'ejs.html'), 'utf8');
    expect(html).toContain('<div class="banner">EJS Banner</div>');
  });

  it('uses a configured layout name', async () => {
    writeTemplate('layouts/wide.hbs', '<html>\n<body class="wide">\n{{{body}}}\n</body>\n</html>');
    writeTemplate('page.hbs', '<h1>{{title}}</h1>\n{{{html}}}');
    writeContent('p.md', '---\ntitle: Wide Page\ntemplate: page\n---\n\n# P');

    await build({ defaultLayout: 'wide' });

    const html = fs.readFileSync(path.join(outputDir(), 'p.html'), 'utf8');
    expect(html).toContain('<body class="wide">');
  });

  it('lets a page override the layout via frontmatter', async () => {
    writeTemplate('layouts/default.hbs', '<html>\n<body class="default-layout">\n{{{body}}}\n</body>\n</html>');
    writeTemplate('layouts/full.hbs', '<html>\n<body class="full-layout">\n{{{body}}}\n</body>\n</html>');
    writeTemplate('page.hbs', '<h1>{{title}}</h1>');
    writeContent('a.md', '---\ntitle: A\ntemplate: page\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\ntemplate: page\nlayout: full\n---\n\n# B');

    await build();

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    const b = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(a).toContain('class="default-layout"');
    expect(b).toContain('class="full-layout"');
    expect(b).not.toContain('class="default-layout"');
  });

  it('renders index.html through the configured layout', async () => {
    writeTemplate('layouts/default.hbs', '<html>\n<body>\n<header>Site: {{title}}</header>\n{{{body}}}\n</body>\n</html>');
    writeContent('a.md', '---\ntitle: Page A\n---\n\n# A');

    await build();

    const index = fs.readFileSync(path.join(outputDir(), 'index.html'), 'utf8');
    expect(index).toContain('<header>Site: Templated Site</header>');
    expect(index).toContain('<a href="a.html">Page A</a>');
  });

  it('falls back to the built-in renderer when the named template is missing', async () => {
    writeTemplate('layouts/default.hbs', '<html>\n<body>\n{{{body}}}\n</body>\n</html>');
    writeContent('p.md', '---\ntitle: Missing Tpl\ntemplate: does-not-exist\n---\n\n# Body');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'p.html'), 'utf8');
    expect(html).toContain('<main>');
    expect(html).toContain('<footer>Generated by Templated Site</footer>');
    expect(html).toContain('<h1>Body</h1>');
  });

  it('falls back to the built-in renderer when no templates exist', async () => {
    writeContent('p.md', '---\ntitle: Plain\n---\n\n# Body');

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'p.html'), 'utf8');
    expect(html).toContain('<main>');
    expect(html).toContain('<h1>Plain</h1>');
    expect(html).toContain('<footer>Generated by Templated Site</footer>');
  });

  it('exposes frontmatter fields to templates', async () => {
    writeTemplate('default.hbs', [
      '<article>',
      '<h1>{{title}}</h1>',
      '<time>{{date}}</time>',
      '{{#each tags}}<span class="tag">{{this}}</span>{{/each}}',
      '{{#if author}}<p class="author">{{author}}</p>{{/if}}',
      '</article>',
    ].join('\n'));
    writeContent('p.md', [
      '---',
      'title: Metadata',
      'date: 2024-03-15',
      'tags:',
      '  - js',
      '  - ts',
      'author: Ada',
      '---',
      '',
      '# Body',
    ].join('\n'));

    await build();

    const html = fs.readFileSync(path.join(outputDir(), 'p.html'), 'utf8');
    expect(html).toContain('<time>2024-03-15</time>');
    expect(html).toContain('<span class="tag">js</span>');
    expect(html).toContain('<span class="tag">ts</span>');
    expect(html).toContain('<p class="author">Ada</p>');
  });
});

describe('detectEngine', () => {
  it('detects the engine from the file extension', () => {
    expect(detectEngine('/templates/page.hbs')).toBe('hbs');
    expect(detectEngine('/templates/page.ejs')).toBe('ejs');
    expect(detectEngine('/templates/page.html')).toBe('html');
    expect(detectEngine('/templates/page')).toBe('hbs');
  });
});

describe('findTemplateFile', () => {
  let tmp: string;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-find-'));
  });

  afterEach(() => {
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it('finds a template by bare name across supported extensions', () => {
    fs.writeFileSync(path.join(tmp, 'default.hbs'), 'x');
    expect(findTemplateFile(tmp, 'default')).toBe(path.join(tmp, 'default.hbs'));
    expect(findTemplateFile(tmp, 'missing')).toBeNull();
  });

  it('accepts an explicit extension', () => {
    fs.writeFileSync(path.join(tmp, 'page.ejs'), 'x');
    expect(findTemplateFile(tmp, 'page.ejs')).toBe(path.join(tmp, 'page.ejs'));
  });
});

describe('renderPage / renderIndex', () => {
  const config = { title: 'Unit Site' };

  function makePage(data: Record<string, unknown> = {}, html = '<h1>Body</h1>'): Page {
    return {
      slug: 'unit',
      link: 'unit.html',
      outputPath: '/out/unit.html',
      filePath: '/content/unit.md',
      data: data as Page['data'],
      content: '# Body',
      html,
      template: data.template as string | undefined,
      layout: data.layout as string | undefined,
    };
  }

  it('renders a page with built-in output when no templates dir is configured', () => {
    const html = renderPage(makePage({ title: 'Unit' }), config);
    expect(html).toContain('<h1>Unit</h1>');
    expect(html).toContain('<title>Unit</title>');
    expect(html).toContain('<footer>Generated by Unit Site</footer>');
  });

  it('uses pageTitle from frontmatter or falls back to the slug', () => {
    expect(pageTitle(makePage({ title: 'T' }))).toBe('T');
    expect(pageTitle(makePage({}))).toBe('unit');
  });

  it('renders an index listing pages', () => {
    const html = renderIndex([makePage({ title: 'Zed' }), makePage({ title: 'Alpha' })], config);
    expect(html).toContain('<a href="unit.html">Zed</a>');
    expect(html).toContain('<a href="unit.html">Alpha</a>');
  });
});
