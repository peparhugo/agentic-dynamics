import { TemplateEngine } from '../src/templates';
import { generatePageHtml, generateIndexHtml } from '../src/generator';
import { build } from '../src/build';
import { parseMarkdownFile } from '../src/parser';
import { Page, Frontmatter } from '../src/types';
import fs from 'fs';
import path from 'path';

const testTemplatesDir = path.join(__dirname, 'templates');
const testBuildDir = path.join(__dirname, 'integration-templates');
const contentDir = path.join(testBuildDir, 'content');
const outputDir = path.join(testBuildDir, 'dist');

function makePage(
  overrides: Partial<Frontmatter> & { slug?: string; html?: string; content?: string },
): Page {
  return {
    frontmatter: {
      title: 'Default Title',
      ...overrides,
    },
    content: overrides.content || '',
    html: overrides.html || '<p>Hello</p>',
    slug: overrides.slug || 'default',
    sourcePath: '/tmp/default.md',
  };
}

describe('TemplateEngine', () => {
  let engine: TemplateEngine;

  beforeEach(() => {
    engine = new TemplateEngine();
  });

  describe('default templates (no custom templates loaded)', () => {
    it('renders a page with default template when no templates dir loaded', () => {
      const page = makePage({ title: 'Hello World', date: '2024-06-01', tags: ['js', 'ts'] });
      const html = engine.renderPage(page);

      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>Hello World</title>');
      expect(html).toContain('<h1>Hello World</h1>');
      expect(html).toContain('<time datetime="2024-06-01">2024-06-01</time>');
      expect(html).toContain('<p>Tags: js, ts</p>');
      expect(html).toContain('<p>Hello</p>');
      expect(html).toContain('<a href="index.html">Home</a>');
    });

    it('renders a page without optional fields', () => {
      const page = makePage({ title: 'Minimal' });
      const html = engine.renderPage(page);

      expect(html).not.toContain('<time');
      expect(html).not.toContain('<p>Tags:');
      expect(html).toContain('<p>Hello</p>');
    });

    it('renders index page', () => {
      const pages = [
        makePage({ title: 'Page 1', slug: 'page1' }),
        makePage({ title: 'Page 2', slug: 'page2', date: '2024-05-10' }),
      ];
      const html = engine.renderIndex(pages);

      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<h1>All Pages</h1>');
      expect(html).toContain('<a href="page1.html">Page 1</a>');
      expect(html).toContain('<a href="page2.html">Page 2</a>');
      expect(html).toContain('2024-05-10');
    });
  });

  describe('with custom templates loaded', () => {
    beforeEach(() => {
      engine.init(testTemplatesDir);
    });

    it('renders page with custom template specified in frontmatter', () => {
      const page = makePage({
        title: 'My Post',
        template: 'post',
        html: '<p>Content here</p>',
      });
      const html = engine.renderPage(page);

      expect(html).toContain('<main class="post">');
      expect(html).toContain('<h1>My Post</h1>');
      expect(html).toContain('<div class="content"><p>Content here</p></div>');
      expect(html).toContain('>&copy; 2024 My Site</p>');
    });

    it('includes partials referenced in templates', () => {
      const page = makePage({
        title: 'Post',
        template: 'post',
        html: '<p>Body</p>',
      });
      const html = engine.renderPage(page);

      expect(html).toContain('<nav><a href="/">Home</a></nav>');
      expect(html).toContain('<p>&copy; 2024 My Site</p>');
    });

    it('falls back to default template when template name not found', () => {
      const page = makePage({
        title: 'Missing Template',
        template: 'nonexistent',
        html: '<p>Body</p>',
      });
      const html = engine.renderPage(page);

      expect(html).toContain('<title>Missing Template</title>');
      expect(html).toContain('<a href="index.html">Home</a>');
    });

    it('renders with custom layout specified in frontmatter', () => {
      const page = makePage({
        title: 'Layout Test',
        layout: 'default',
        html: '<p>Wrapped content</p>',
      });
      const html = engine.renderPage(page);

      expect(html).toContain('<h1>Site Name</h1>');
      expect(html).toContain('<p>Wrapped content</p>');
      expect(html).toContain('<p>Footer</p>');
    });

    it('layout wraps the full page output', () => {
      const page = makePage({
        title: 'Wrapped',
        layout: 'default',
        html: '<p>Inner</p>',
      });
      const html = engine.renderPage(page);

      expect(html).toContain('<h1>Site Name</h1>');
      expect(html).toContain('<title>Wrapped</title>');
      expect(html).toContain('<h1>Wrapped</h1>');
      expect(html).toContain('<p>Inner</p>');
      expect(html).toContain('<p>Footer</p>');
    });

    it('falls back to passthrough layout when layout name not found', () => {
      const page = makePage({
        title: 'No Layout',
        layout: 'nonexistent',
        html: '<p>Body</p>',
      });
      const html = engine.renderPage(page);

      expect(html).not.toContain('Site Name');
      expect(html).not.toContain('Footer');
      expect(html).toContain('<p>Body</p>');
    });

    it('combines custom template and layout', () => {
      const page = makePage({
        title: 'Full Test',
        template: 'custom',
        layout: 'default',
        html: '<p>The body</p>',
      });
      const html = engine.renderPage(page);

      expect(html).toContain('<h1>Site Name</h1>');
      expect(html).toContain('<h1>Full Test</h1>');
      expect(html).toContain('<p>The body</p>');
      expect(html).toContain('<p>Footer</p>');
      expect(html).toContain('class="custom"');
    });

    it('renders index with default template even when custom templates loaded', () => {
      const pages = [
        makePage({ title: 'A', slug: 'a' }),
        makePage({ title: 'B', slug: 'b' }),
      ];
      const html = engine.renderIndex(pages);

      expect(html).toContain('<h1>All Pages</h1>');
      expect(html).toContain('<a href="a.html">A</a>');
      expect(html).toContain('<a href="b.html">B</a>');
    });
  });
});

describe('generatePageHtml with template engine', () => {
  it('uses engine when provided', () => {
    const engine = new TemplateEngine();
    engine.init(testTemplatesDir);

    const page = makePage({
      title: 'Engine Test',
      template: 'post',
      html: '<p>Rendered</p>',
    });
    const html = generatePageHtml(page, engine);

    expect(html).toContain('<main class="post">');
    expect(html).toContain('<p>&copy; 2024 My Site</p>');
  });

  it('falls back to inline when no engine', () => {
    const page = makePage({ title: 'No Engine', html: '<p>Body</p>' });
    const html = generatePageHtml(page);

    expect(html).toContain('<a href="index.html">Home</a>');
    expect(html).toContain('<h1>No Engine</h1>');
  });
});

describe('generateIndexHtml with template engine', () => {
  it('uses engine when provided', () => {
    const engine = new TemplateEngine();
    const pages = [
      makePage({ title: 'Page A', slug: 'page-a' }),
      makePage({ title: 'Page B', slug: 'page-b' }),
    ];
    const html = generateIndexHtml(pages, engine);

    expect(html).toContain('<h1>All Pages</h1>');
    expect(html).toContain('<a href="page-a.html">Page A</a>');
    expect(html).toContain('<a href="page-b.html">Page B</a>');
  });

  it('falls back to inline when no engine', () => {
    const pages = [makePage({ title: 'X', slug: 'x' })];
    const html = generateIndexHtml(pages);

    expect(html).toContain('<h1>All Pages</h1>');
    expect(html).toContain('<a href="x.html">X</a>');
  });
});

describe('build with templates', () => {
  beforeEach(() => {
    if (fs.existsSync(testBuildDir)) {
      fs.rmSync(testBuildDir, { recursive: true, force: true });
    }
    fs.mkdirSync(contentDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testBuildDir)) {
      fs.rmSync(testBuildDir, { recursive: true, force: true });
    }
  });

  it('uses templates when templatesDir is provided', () => {
    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      `---
title: Template Post
date: 2024-06-15
template: post
---
# Heading

Body text.`,
    );

    build({ contentDir, outputDir, templatesDir: testTemplatesDir });

    const postPath = path.join(outputDir, 'post.html');
    expect(fs.existsSync(postPath)).toBe(true);

    const html = fs.readFileSync(postPath, 'utf-8');
    expect(html).toContain('<main class="post">');
    expect(html).toContain('<h1>Template Post</h1>');
    expect(html).toContain('<h1>Heading</h1>');
    expect(html).toContain('<p>Body text.</p>');
    expect(html).toContain('<nav><a href="/">Home</a></nav>');
    expect(html).toContain('>&copy; 2024 My Site</p>');
  });

  it('still works without templatesDir (backward compatibility)', () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      `---
title: No Templates
---
Plain content.`,
    );

    build({ contentDir, outputDir });

    const pagePath = path.join(outputDir, 'page.html');
    expect(fs.existsSync(pagePath)).toBe(true);

    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<title>No Templates</title>');
    expect(html).toContain('<a href="index.html">Home</a>');
  });

  it('generates index.html even when templates are used', () => {
    fs.writeFileSync(
      path.join(contentDir, 'a.md'),
      `---
title: Alpha
---
A`,
    );

    build({ contentDir, outputDir, templatesDir: testTemplatesDir });

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const html = fs.readFileSync(indexPath, 'utf-8');
    expect(html).toContain('<a href="a.html">Alpha</a>');
    expect(html).toContain('<h1>All Pages</h1>');
  });
});

describe('parseMarkdownFile with template frontmatter', () => {
  const testContentDir = path.join(__dirname, 'template-content');

  beforeEach(() => {
    if (fs.existsSync(testContentDir)) {
      fs.rmSync(testContentDir, { recursive: true, force: true });
    }
    fs.mkdirSync(testContentDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testContentDir)) {
      fs.rmSync(testContentDir, { recursive: true, force: true });
    }
  });

  it('extracts template from frontmatter', () => {
    const md = `---
title: With Template
template: post
---
Content`;

    const filePath = path.join(testContentDir, 'templated.md');
    fs.writeFileSync(filePath, md, 'utf-8');

    const page = parseMarkdownFile(filePath);
    expect(page.frontmatter.template).toBe('post');
  });

  it('extracts layout from frontmatter', () => {
    const md = `---
title: With Layout
layout: default
---
Content`;

    const filePath = path.join(testContentDir, 'layout.md');
    fs.writeFileSync(filePath, md, 'utf-8');

    const page = parseMarkdownFile(filePath);
    expect(page.frontmatter.layout).toBe('default');
  });

  it('template and layout are undefined when not specified', () => {
    const md = `---
title: Plain
---
Content`;

    const filePath = path.join(testContentDir, 'plain.md');
    fs.writeFileSync(filePath, md, 'utf-8');

    const page = parseMarkdownFile(filePath);
    expect(page.frontmatter.template).toBeUndefined();
    expect(page.frontmatter.layout).toBeUndefined();
  });
});

describe('TemplateEngine init with missing directory', () => {
  it('does not throw when templatesDir does not exist', () => {
    const engine = new TemplateEngine();
    expect(() => engine.init('/nonexistent/templates/path')).not.toThrow();

    const page = makePage({ title: 'Test', html: '<p>Body</p>' });
    const html = engine.renderPage(page);
    expect(html).toContain('<title>Test</title>');
  });
});
