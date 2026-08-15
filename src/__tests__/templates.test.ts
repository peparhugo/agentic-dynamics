import fs from 'fs';
import os from 'os';
import path from 'path';

import { buildSite } from '../site';
import {
  DEFAULT_LAYOUT,
  DEFAULT_TEMPLATE,
  TEMPLATE_EXTENSION,
  hasTemplates,
  loadTemplates,
  pageContext,
  renderIndexWithTemplates,
  renderPageWithTemplates,
  renderTemplateFile,
  resolveTemplateName,
} from '../templates';
import type { Page } from '../types';

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

function makeFixture(
  templateFiles: Record<string, string>,
  contentFiles: Record<string, string>,
): { root: string; templatesDir: string; contentDir: string; outputDir: string } {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
  const templatesDir = path.join(root, 'templates');
  const contentDir = path.join(root, 'content');
  const outputDir = path.join(root, 'dist');
  writeTree(templatesDir, templateFiles);
  writeTree(contentDir, contentFiles);
  return { root, templatesDir, contentDir, outputDir };
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'x',
    sourcePath: 'x.md',
    outputName: 'x.html',
    title: 'X',
    tags: [],
    html: '<p>hello</p>',
    content: 'hello',
    raw: 'hello',
    data: { title: 'X' },
    ...overrides,
  };
}

const DEFAULT_LAYOUT_FILE = `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>
{{> header}}
<main>
{{{body}}}
</main>
</body>
</html>`;

const DEFAULT_TEMPLATE_FILE = `<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>{{/if}}
{{#each tags}}<span class="tag">{{this}}</span>{{/each}}
{{{body}}}`;

const HEADER_PARTIAL = '<header class="site-header">Site Header</header>';

describe('resolveTemplateName', () => {
  it('appends the extension when it is missing', () => {
    expect(resolveTemplateName('post')).toBe('post.hbs');
    expect(resolveTemplateName(DEFAULT_TEMPLATE)).toBe('default.hbs');
    expect(resolveTemplateName(DEFAULT_LAYOUT)).toBe('default.hbs');
  });

  it('keeps an existing extension', () => {
    expect(resolveTemplateName('post.hbs')).toBe('post.hbs');
    expect(resolveTemplateName('post.HBS')).toBe('post.HBS');
  });

  it('trims surrounding whitespace', () => {
    expect(resolveTemplateName('  post  ')).toBe('post.hbs');
  });

  it('supports a custom extension', () => {
    expect(resolveTemplateName('post', 'ejs')).toBe('post.ejs');
  });
});

describe('hasTemplates / loadTemplates', () => {
  it('detects whether a templates directory exists', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
    expect(hasTemplates(dir)).toBe(true);
    expect(hasTemplates(path.join(dir, 'missing'))).toBe(false);
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('loads and compiles templates, layouts and partials', () => {
    const fixture = makeFixture(
      {
        'default.hbs': 'page {{title}}',
        'layouts/default.hbs': 'layout {{{body}}}',
        'partials/header.hbs': 'header',
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      expect(templates.dir).toBe(fixture.templatesDir);
      expect(templates.templates.has('default.hbs')).toBe(true);
      expect(templates.layouts.has('default.hbs')).toBe(true);
      expect(templates.partials.has('header')).toBe(true);

      expect(
        renderTemplateFile(templates, 'templates', 'default.hbs', { title: 'T' }),
      ).toContain('page T');
      expect(
        renderTemplateFile(templates, 'layouts', 'default.hbs', { body: 'B' }),
      ).toContain('layout B');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });
});

describe('pageContext', () => {
  it('exposes page data merged with frontmatter values', () => {
    const context = pageContext(
      makePage({ data: { title: 'X', layout: 'minimal', custom: 'yes' } }),
    );
    expect(context.title).toBe('X');
    expect(context.body).toBe('<p>hello</p>');
    expect(context.content).toBe('hello');
    expect(context.slug).toBe('x');
    expect(context.outputName).toBe('x.html');
    expect(context.layout).toBe('minimal');
    expect(context.custom).toBe('yes');
  });
});

describe('renderPageWithTemplates', () => {
  it('uses the default template and layout when the page declares none', () => {
    const fixture = makeFixture(
      {
        'default.hbs': DEFAULT_TEMPLATE_FILE,
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({
        title: 'Hello',
        date: '2026-05-01',
        tags: ['a', 'b'],
        html: '<p>Body text.</p>',
        data: { title: 'Hello', date: '2026-05-01', tags: ['a', 'b'] },
      });

      const html = renderPageWithTemplates(page, templates);
      expect(html).toContain('<title>Hello</title>');
      expect(html).toContain('<h1>Hello</h1>');
      expect(html).toContain('<p class="date">2026-05-01</p>');
      expect(html).toContain('<span class="tag">a</span>');
      expect(html).toContain('<span class="tag">b</span>');
      expect(html).toContain('<p>Body text.</p>');
      expect(html).not.toContain('{{{body}}}');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('uses the template named in frontmatter', () => {
    const fixture = makeFixture(
      {
        'post.hbs': '<article>{{title}}</article>',
        'default.hbs': 'default {{title}}',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({ data: { title: 'X', template: 'post' } });
      const html = renderPageWithTemplates(page, templates);
      expect(html).toContain('<article>X</article>');
      expect(html).not.toContain('default X');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('accepts a template name that already has the extension', () => {
    const fixture = makeFixture(
      {
        'post.hbs': '<article>{{title}}</article>',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({ data: { title: 'X', template: 'post.hbs' } });
      expect(renderPageWithTemplates(page, templates)).toContain('<article>X</article>');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('uses the layout named in frontmatter', () => {
    const fixture = makeFixture(
      {
        'default.hbs': DEFAULT_TEMPLATE_FILE,
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'layouts/minimal.hbs': '<div id="minimal">{{{body}}}</div>',
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({ data: { title: 'X', layout: 'minimal' } });
      const html = renderPageWithTemplates(page, templates);
      expect(html).toContain('<div id="minimal">');
      expect(html).toContain('<h1>X</h1>');
      expect(html).not.toContain('<html>');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('renders partials referenced from templates and layouts', () => {
    const fixture = makeFixture(
      {
        'default.hbs': '{{> nav}}<main>{{{body}}}</main>',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
        'partials/nav.hbs': '<nav>Nav Links</nav>',
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const html = renderPageWithTemplates(makePage({ title: 'T' }), templates);
      expect(html).toContain('Site Header');
      expect(html).toContain('<nav>Nav Links</nav>');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('escapes interpolated frontmatter values', () => {
    const fixture = makeFixture(
      {
        'default.hbs': '<h1>{{title}}</h1>{{{body}}}',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({
        title: '<script>alert(1)</script>',
        data: { title: '<script>alert(1)</script>' },
      });
      const html = renderPageWithTemplates(page, templates);
      expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
      expect(html).not.toContain('<script>alert(1)</script>');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('renders the markdown body unescaped through the body placeholder', () => {
    const fixture = makeFixture(
      {
        'default.hbs': '{{#if date}}<p class="date">{{date}}</p>{{/if}}{{{body}}}',
        'layouts/default.hbs': '<div class="wrap">{{{body}}}</div>',
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({
        date: '2026-01-01',
        html: '<p><b>raw</b> &amp; html</p>',
        data: { date: '2026-01-01' },
      });
      const html = renderPageWithTemplates(page, templates);
      expect(html).toContain('<p><b>raw</b> &amp; html</p>');
      expect(html).toContain('<p class="date">2026-01-01</p>');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('throws a descriptive error for a missing template', () => {
    const fixture = makeFixture(
      { 'layouts/default.hbs': DEFAULT_LAYOUT_FILE },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({ data: { title: 'X', template: 'post' } });
      expect(() => renderPageWithTemplates(page, templates)).toThrow(
        /Template not found: templates\/post\.hbs/,
      );
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('throws a descriptive error for a missing layout', () => {
    const fixture = makeFixture({ 'default.hbs': '<h1>{{title}}</h1>' }, {});

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const page = makePage({ data: { title: 'X' } });
      expect(() => renderPageWithTemplates(page, templates)).toThrow(
        /Template not found: layouts\/default\.hbs/,
      );
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });
});

describe('renderIndexWithTemplates', () => {
  it('renders the index through index.hbs wrapped in the default layout', () => {
    const fixture = makeFixture(
      {
        'index.hbs':
          '{{#each pages}}<li><a href="{{outputName}}">{{title}}</a></li>{{else}}<li>None</li>{{/each}}',
        'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
      },
      {},
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      const pages = [
        makePage({ slug: 'a', outputName: 'a.html', title: 'A' }),
        makePage({ slug: 'b', outputName: 'b.html', title: 'B' }),
      ];
      const html = renderIndexWithTemplates(pages, templates);
      expect(html).toContain('<html><body>');
      expect(html).toContain('<li><a href="a.html">A</a></li>');
      expect(html).toContain('<li><a href="b.html">B</a></li>');
      expect(html).not.toContain('{{{body}}}');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });
});

describe('buildSite with templates', () => {
  it('renders every page through templates and an index via index.hbs', () => {
    const fixture = makeFixture(
      {
        'default.hbs': DEFAULT_TEMPLATE_FILE,
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
        'index.hbs':
          '{{#each pages}}<li><a href="{{outputName}}">{{title}}</a></li>{{/each}}',
      },
      {
        'hello.md': '---\ntitle: Hello World\ndate: 2026-05-01\ntags: a, b\n---\n# Greeting',
      },
    );

    try {
      const pages = buildSite({
        contentDir: fixture.contentDir,
        outputDir: fixture.outputDir,
        templatesDir: fixture.templatesDir,
      });

      expect(pages).toHaveLength(1);

      const pageHtml = fs.readFileSync(path.join(fixture.outputDir, 'hello.html'), 'utf8');
      expect(pageHtml).toContain('<h1>Hello World</h1>');
      expect(pageHtml).toContain('Site Header');
      expect(pageHtml).toContain('<h1>Greeting</h1>');
      expect(pageHtml).toContain('<span class="tag">a</span>');

      const indexHtml = fs.readFileSync(path.join(fixture.outputDir, 'index.html'), 'utf8');
      expect(indexHtml).toContain('href="hello.html"');
      expect(indexHtml).toContain('<li><a href="hello.html">Hello World</a></li>');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('falls back to the built-in index when no index.hbs exists', () => {
    const fixture = makeFixture(
      {
        'default.hbs': '<h1>{{title}}</h1>{{{body}}}',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
      },
      { 'a.md': '---\ntitle: Alpha\n---\nBody' },
    );

    try {
      buildSite({
        contentDir: fixture.contentDir,
        outputDir: fixture.outputDir,
        templatesDir: fixture.templatesDir,
      });

      const indexHtml = fs.readFileSync(path.join(fixture.outputDir, 'index.html'), 'utf8');
      expect(indexHtml).toContain('href="a.html"');
      expect(indexHtml).toContain('Alpha');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('uses the built-in renderers when the templates directory is missing', () => {
    const fixture = makeFixture({}, { 'a.md': '---\ntitle: Alpha\n---\nBody' });

    try {
      const pages = buildSite({
        contentDir: fixture.contentDir,
        outputDir: fixture.outputDir,
        templatesDir: path.join(fixture.root, 'does-not-exist'),
      });

      expect(pages).toHaveLength(1);
      const html = fs.readFileSync(path.join(fixture.outputDir, 'a.html'), 'utf8');
      expect(html).toContain('<h1>Alpha</h1>');
      expect(html).toContain('href="index.html"');
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it('uses the default templates directory when none is given', () => {
    const fixture = makeFixture(
      {
        'default.hbs': '<h1>{{title}}</h1>{{{body}}}',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'partials/header.hbs': HEADER_PARTIAL,
      },
      { 'a.md': '---\ntitle: Alpha\n---\nBody' },
    );
    const previousCwd = process.cwd();
    process.chdir(fixture.root);

    try {
      const pages = buildSite({ contentDir: fixture.contentDir, outputDir: fixture.outputDir });
      expect(pages).toHaveLength(1);
      const html = fs.readFileSync(path.join(fixture.outputDir, 'a.html'), 'utf8');
      expect(html).toContain('<h1>Alpha</h1>');
    } finally {
      process.chdir(previousCwd);
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });

  it(`only loads ${TEMPLATE_EXTENSION} files from the templates directory`, () => {
    const fixture = makeFixture(
      {
        'default.hbs': '<h1>{{title}}</h1>',
        'layouts/default.hbs': DEFAULT_LAYOUT_FILE,
        'readme.txt': 'ignored',
      },
      { 'a.md': '---\ntitle: Alpha\n---\nBody' },
    );

    try {
      const templates = loadTemplates(fixture.templatesDir);
      expect(templates.templates.has('readme.txt')).toBe(false);
      expect(templates.templates.has('default.hbs')).toBe(true);
    } finally {
      fs.rmSync(fixture.root, { recursive: true, force: true });
    }
  });
});
