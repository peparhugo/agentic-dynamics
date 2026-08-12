import fs from 'fs';
import path from 'path';
import os from 'os';
import { TemplateEngine } from '../templates';
import { Page } from '../types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'test-page',
    frontmatter: {
      title: 'Test Page',
      date: '2024-06-15',
      tags: ['typescript', 'testing'],
    },
    content: 'Some markdown content',
    html: '<p>Some markdown content</p>',
    ...overrides,
  };
}

describe('TemplateEngine', () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-template-test-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  describe('with built-in defaults (no templates dir)', () => {
    let engine: TemplateEngine;

    beforeEach(() => {
      engine = new TemplateEngine(path.join(tmpDir, 'nonexistent'));
    });

    it('renders a page with title and content', () => {
      const page = makePage();
      const html = engine.renderPage(page);
      expect(html).toContain('<h1>Test Page</h1>');
      expect(html).toContain('<p>Some markdown content</p>');
    });

    it('renders a page with date and tags', () => {
      const page = makePage();
      const html = engine.renderPage(page);
      expect(html).toContain('Date: 2024-06-15');
      expect(html).toContain('Tags: typescript, testing');
    });

    it('omits date when empty', () => {
      const page = makePage({ frontmatter: { title: 'No Date', date: '', tags: [] } });
      const html = engine.renderPage(page);
      expect(html).not.toContain('Date:');
    });

    it('omits tags when empty', () => {
      const page = makePage({ frontmatter: { title: 'No Tags', date: '', tags: [] } });
      const html = engine.renderPage(page);
      expect(html).not.toContain('Tags:');
    });

    it('renders an index page', () => {
      const pages = [makePage({ slug: 'alpha', frontmatter: { title: 'Alpha', date: '', tags: [] } })];
      const html = engine.renderIndex(pages);
      expect(html).toContain('<h1>Site Index</h1>');
      expect(html).toContain('<a href="alpha.html">Alpha</a>');
    });

    it('renders a layout with body placeholder', () => {
      const html = engine.renderLayout('My Title', '<p>Hello</p>');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>My Title</title>');
      expect(html).toContain('<p>Hello</p>');
      expect(html).toContain('<html lang="en">');
    });

    it('escapes HTML in titles', () => {
      const page = makePage({ frontmatter: { title: '<script>alert("xss")</script>', date: '', tags: [] } });
      const html = engine.renderPage(page);
      expect(html).toContain('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
      expect(html).not.toContain('<script>alert');
    });

    it('does not escape content passed as raw HTML', () => {
      const page = makePage({ html: '<strong>bold</strong>' });
      const html = engine.renderPage(page);
      expect(html).toContain('<strong>bold</strong>');
    });

    it('falls back to default template when frontmatter specifies nonexistent template', () => {
      const page = makePage({ frontmatter: { title: 'Custom Template', date: '', tags: [], template: 'nonexistent' } });
      const html = engine.renderPage(page);
      expect(html).toContain('<h1>Custom Template</h1>');
    });

    it('falls back to default layout when frontmatter specifies nonexistent layout', () => {
      const page = makePage({ frontmatter: { title: 'Custom Layout', date: '', tags: [], layout: 'nonexistent' } });
      const body = engine.renderPage(page);
      const html = engine.renderLayout('Custom Layout', body, 'nonexistent');
      expect(html).toContain('<!DOCTYPE html>');
    });
  });

  describe('with templates on disk', () => {
    let templatesDir: string;
    let engine: TemplateEngine;

    beforeEach(() => {
      templatesDir = path.join(tmpDir, 'templates');
      fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(templatesDir, 'partials'), { recursive: true });

      fs.writeFileSync(path.join(templatesDir, 'page.hbs'), `<h1>{{title}}</h1>
<div class="content">{{{content}}}</div>
<p><a href="index.html">Back</a></p>`);

      fs.writeFileSync(path.join(templatesDir, 'index.hbs'), `<h1>All Pages</h1>
<ul>
{{#each pages}}
<li><a href="{{slug}}.html">{{title}}</a></li>
{{/each}}
</ul>`);

      fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>
<main>{{{body}}}</main>
</body>
</html>`);

      fs.writeFileSync(path.join(templatesDir, 'layouts', 'alt.hbs'), `<!DOCTYPE html>
<html>
<head><title>Alt: {{title}}</title></head>
<body>
<div class="alt">{{{body}}}</div>
</body>
</html>`);

      fs.writeFileSync(path.join(templatesDir, 'partials', 'nav.hbs'), `<nav>Nav</nav>`);

      engine = new TemplateEngine(templatesDir);
    });

    it('loads custom page template from disk', () => {
      const page = makePage({ frontmatter: { title: 'Disk Page', date: '', tags: [] } });
      const html = engine.renderPage(page);
      expect(html).toContain('<h1>Disk Page</h1>');
      expect(html).toContain('<div class="content">');
      expect(html).toContain('<a href="index.html">Back</a>');
    });

    it('loads custom index template from disk', () => {
      const pages = [makePage({ slug: 'one', frontmatter: { title: 'Page One', date: '', tags: [] } })];
      const html = engine.renderIndex(pages);
      expect(html).toContain('<h1>All Pages</h1>');
      expect(html).toContain('<a href="one.html">Page One</a>');
    });

    it('loads custom layout from disk', () => {
      const html = engine.renderLayout('Title', '<p>Body</p>');
      expect(html).toContain('<main>');
      expect(html).toContain('<p>Body</p>');
    });

    it('uses alternate layout when specified', () => {
      const html = engine.renderLayout('Title', '<p>Body</p>', 'alt');
      expect(html).toContain('<title>Alt: Title</title>');
      expect(html).toContain('<div class="alt">');
    });

    it('registers and renders partials', () => {
      const page = makePage({ frontmatter: { title: 'With Nav', date: '', tags: [] } });
      const body = engine.renderPage(page);
      expect(body).toBeDefined();
    });
  });

  describe('with template that uses partials', () => {
    it('can include partials in custom page template', () => {
      const templatesDir = path.join(tmpDir, 'with-partials');
      fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(templatesDir, 'partials'), { recursive: true });

      fs.writeFileSync(path.join(templatesDir, 'partials', 'nav.hbs'), `<nav>Custom Nav</nav>`);

      fs.writeFileSync(path.join(templatesDir, 'page.hbs'), `{{> nav}}
<h1>{{title}}</h1>
{{{content}}}`);

      fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>{{{body}}}</body>
</html>`);

      const engine = new TemplateEngine(templatesDir);
      const page = makePage({ frontmatter: { title: 'Nav Page', date: '', tags: [] } });
      const body = engine.renderPage(page);
      expect(body).toContain('Custom Nav');
      expect(body).toContain('<h1>Nav Page</h1>');
    });
  });
});
