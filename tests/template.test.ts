import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  TemplateEngine,
  pageToContext,
} from '../src/template';
import {
  renderPageWithEngine,
  renderIndexWithEngine,
  buildSite,
} from '../src/builder';
import { parseMarkdown } from '../src/markdown';
import { Page } from '../src/types';

const REPO_TEMPLATES = path.join(__dirname, '..', 'templates');

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

function writeFile(root: string, rel: string, content: string): void {
  const full = path.join(root, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content, 'utf8');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'post',
    title: 'Post',
    tags: [],
    content: '<p>Body</p>',
    ...overrides,
  };
}

function writeTemplates(root: string): void {
  writeFile(root, 'default.hbs', '<article><h1>{{title}}</h1>{{{content}}}</article>');
  writeFile(
    root,
    'layouts/default.hbs',
    '<html><head><title>{{title}}</title></head><body>{{> header}}{{{body}}}{{> footer}}</body></html>',
  );
  writeFile(root, 'partials/header.hbs', '<header>HEADER</header>');
  writeFile(root, 'partials/footer.hbs', '<footer>FOOTER</footer>');
}

describe('TemplateEngine', () => {
  it('loads templates, layouts and partials from the templates directory', () => {
    const engine = new TemplateEngine(REPO_TEMPLATES);
    expect(engine.enabled).toBe(true);
    expect(engine.hasTemplate('default')).toBe(true);
    expect(engine.hasLayout('default')).toBe(true);
    expect(engine.getIndexTemplate()).toBeDefined();
  });

  it('is disabled when the templates directory does not exist', () => {
    const engine = new TemplateEngine(path.join(makeTempDir(), 'nope'));
    expect(engine.enabled).toBe(false);
  });

  it('builds a context from a page', () => {
    const page = makePage({
      date: '2026-01-01',
      tags: ['a', 'b'],
      data: { author: 'Alice' },
    });
    const ctx = pageToContext(page);
    expect(ctx.title).toBe('Post');
    expect(ctx.tags).toEqual(['a', 'b']);
    expect(ctx.page.author).toBe('Alice');
    expect(ctx.page.content).toBe('<p>Body</p>');
  });
});

describe('renderPageWithEngine', () => {
  it('renders a template selected by the page template field', () => {
    const root = makeTempDir();
    writeFile(root, 'post.hbs', '<div class="post"><h2>{{title}}</h2>{{{content}}}</div>');

    const engine = new TemplateEngine(root);
    const page = makePage({ template: 'post' });
    const html = renderPageWithEngine(page, engine);
    expect(html).toContain('<div class="post">');
    expect(html).toContain('<h2>Post</h2>');
    expect(html).toContain('<p>Body</p>');
  });

  it('uses the default template when none is specified', () => {
    const root = makeTempDir();
    writeFile(root, 'default.hbs', '<main>{{{content}}}</main>');

    const engine = new TemplateEngine(root);
    const html = renderPageWithEngine(makePage(), engine);
    expect(html).toContain('<main>');
    expect(html).toContain('<p>Body</p>');
  });

  it('falls back to the built-in page body when no template exists', () => {
    const root = makeTempDir();
    writeFile(root, 'layouts/default.hbs', '<html><body>{{{body}}}</body></html>');

    const engine = new TemplateEngine(root);
    const html = renderPageWithEngine(makePage(), engine);
    expect(html).toContain('<article>');
    expect(html).toContain('<h1>Post</h1>');
  });

  it('wraps page content in a layout using the body placeholder', () => {
    const root = makeTempDir();
    writeTemplates(root);

    const engine = new TemplateEngine(root);
    const page = makePage({ date: '2026-01-15', tags: ['x'] });
    const html = renderPageWithEngine(page, engine);
    expect(html).toContain('<title>Post</title>');
    expect(html).toContain('<h1>Post</h1>');
    expect(html.indexOf('<article>')).toBeGreaterThan(html.indexOf('<body>'));
    expect(html).toContain('<p>Body</p>');
  });

  it('uses a layout selected by the page layout field', () => {
    const root = makeTempDir();
    writeTemplates(root);
    writeFile(root, 'layouts/wide.hbs', '<html><body class="wide">{{{body}}}</body></html>');

    const engine = new TemplateEngine(root);
    const html = renderPageWithEngine(makePage({ layout: 'wide' }), engine);
    expect(html).toContain('class="wide"');
    expect(html).not.toContain('<title>Post</title>');
  });

  it('renders partials inside layouts', () => {
    const root = makeTempDir();
    writeTemplates(root);

    const engine = new TemplateEngine(root);
    const html = renderPageWithEngine(makePage(), engine);
    expect(html).toContain('<header>HEADER</header>');
    expect(html).toContain('<footer>FOOTER</footer>');
  });

  it('supports EJS templates and layouts', () => {
    const root = makeTempDir();
    writeFile(
      root,
      'default.ejs',
      '<article><h1><%= title %></h1><%- content %></article>',
    );
    writeFile(
      root,
      'layouts/default.ejs',
      '<html><head><title><%= title %></title></head><body><%- include("partials/nav") %><%- body %></body></html>',
    );
    writeFile(root, 'partials/nav.ejs', '<nav>NAV</nav>');

    const engine = new TemplateEngine(root);
    const page = makePage({ title: 'EJS Post' });
    const html = renderPageWithEngine(page, engine);
    expect(html).toContain('<title>EJS Post</title>');
    expect(html).toContain('<h1>EJS Post</h1>');
    expect(html).toContain('<nav>NAV</nav>');
    expect(html).toContain('<p>Body</p>');
  });
});

describe('renderIndexWithEngine', () => {
  it('uses an index template when present', () => {
    const root = makeTempDir();
    writeFile(root, 'index.hbs', '<ul>{{#each pages}}<li>{{this.title}}</li>{{/each}}</ul>');

    const engine = new TemplateEngine(root);
    const pages = [makePage({ slug: 'a', title: 'A' }), makePage({ slug: 'b', title: 'B' })];
    const html = renderIndexWithEngine(pages, engine);
    expect(html).toContain('<li>A</li>');
    expect(html).toContain('<li>B</li>');
  });

  it('falls back to the built-in index when no index template exists', () => {
    const root = makeTempDir();
    writeFile(root, 'default.hbs', '<article>{{{content}}}</article>');

    const engine = new TemplateEngine(root);
    const html = renderIndexWithEngine([makePage({ slug: 'a', title: 'A' })], engine);
    expect(html).toContain('<h1>Pages</h1>');
    expect(html).toContain('href="a.html">A</a>');
  });
});

describe('markdown frontmatter', () => {
  it('parses template and layout fields', () => {
    const doc = parseMarkdown(
      'post',
      `---
title: Post
template: special
layout: wide
---
# Post
`,
    );
    expect(doc.template).toBe('special');
    expect(doc.layout).toBe('wide');
  });

  it('leaves template and layout undefined when absent', () => {
    const doc = parseMarkdown('post', '# Post');
    expect(doc.template).toBeUndefined();
    expect(doc.layout).toBeUndefined();
  });
});

describe('buildSite with templates', () => {
  it('uses templates when a templates directory is provided', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');

    writeFile(
      contentDir,
      'hello.md',
      `---
title: Hello
---
# Hello
`,
    );
    writeTemplates(templatesDir);

    const pages = buildSite(contentDir, outputDir, templatesDir);
    expect(pages).toHaveLength(1);
    const html = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<header>HEADER</header>');
  });

  it('passes templates via options object', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\n# A');
    writeFile(templatesDir, 'default.hbs', '<section>{{{content}}}</section>');

    const pages = buildSite(contentDir, outputDir, { templatesDir });
    expect(pages).toHaveLength(1);
    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<section>');
    expect(html).toContain('<h1>A</h1>');
  });

  it('falls back to built-in rendering when the templates directory is missing', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\n# A');

    buildSite(contentDir, outputDir, path.join(root, 'missing-templates'));
    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<h1>A</h1>');
  });
});
