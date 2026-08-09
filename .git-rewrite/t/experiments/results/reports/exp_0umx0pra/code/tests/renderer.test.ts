import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { renderPage, renderTagPage, setupHandlebars } from '../src/renderer';
import { SiteConfig, PageData } from '../src/types';
import path from 'path';
import fs from 'fs';
import os from 'os';

const fixturesDir = path.join(__dirname, '..', 'test-fixtures');
const templateDir = path.join(fixturesDir, 'templates');

const baseConfig: SiteConfig = {
  sourceDir: path.join(fixturesDir, 'source'),
  templateDir,
  outputDir: fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-output-')),
  devMode: false,
  port: 3000,
  includeDrafts: false,
  siteTitle: 'Test Site',
  siteUrl: 'http://localhost:3000',
};

const samplePage: PageData = {
  frontmatter: {
    title: 'Hello World',
    date: '2024-01-15',
    tags: ['javascript', 'tutorial'],
    draft: false,
    template: 'post',
    layout: 'base',
  },
  html: '<p>Hello World content</p>',
  markdown: 'Hello World content',
  sourcePath: '/test/source/posts/hello-world.md',
  relativePath: 'posts/hello-world.md',
  outputPath: 'posts/hello-world/index.html',
  url: '/posts/hello-world',
  slug: 'posts/hello-world',
  tags: ['javascript', 'tutorial'],
  isDraft: false,
};

describe('template rendering', () => {
  beforeAll(() => {
    setupHandlebars(baseConfig);
  });

  it('renders a page with a named template', () => {
    const html = renderPage(samplePage, [samplePage], baseConfig);
    expect(html).toContain('<article');
    expect(html).toContain('Hello World');
  });

  it('renders page content as HTML', () => {
    const html = renderPage(samplePage, [samplePage], baseConfig);
    expect(html).toContain('<p>Hello World content</p>');
  });

  it('renders a page without layout when none specified', () => {
    const noLayoutPage: PageData = {
      ...samplePage,
      frontmatter: { title: 'No Layout', template: 'default' },
    };
    const html = renderPage(noLayoutPage, [noLayoutPage], baseConfig);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>No Layout</title>');
    expect(html).not.toContain('<header>');
    expect(html).not.toContain('<footer>');
  });

  it('renders a page with layout', () => {
    const html = renderPage(samplePage, [samplePage], baseConfig);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Hello World - Test Site</title>');
  });

  it('renders partials inside layout', () => {
    const html = renderPage(samplePage, [samplePage], baseConfig);
    expect(html).toContain('<header>');
    expect(html).toContain('<nav>');
    expect(html).toContain('Home');
    expect(html).toContain('About');
    expect(html).toContain('<footer>');
    expect(html).toContain('&copy; 2024');
  });

  it('renders tags as links', () => {
    const html = renderPage(samplePage, [samplePage], baseConfig);
    expect(html).toContain('/tags/javascript/');
    expect(html).toContain('/tags/tutorial/');
  });

  it('renders tag page with tagged posts', () => {
    const html = renderTagPage('javascript', [samplePage], [samplePage], baseConfig);
    expect(html).toContain('Posts tagged: javascript');
    expect(html).toContain('Hello World');
    expect(html).toContain('/posts/hello-world');
  });

  it('formats dates with formatDate helper', () => {
    const html = renderPage(samplePage, [samplePage], baseConfig);
    expect(html).toContain('January 15, 2024');
  });

  it('throws for nonexistent template', () => {
    const badPage: PageData = {
      ...samplePage,
      frontmatter: { title: 'Bad', template: 'nonexistent' },
    };
    expect(() => renderPage(badPage, [badPage], baseConfig)).toThrow(
      'Template not found'
    );
  });

  it('uses fallback template when default.hbs does not exist', () => {
    const configNoDefault: SiteConfig = {
      ...baseConfig,
      templateDir: '/nonexistent/dir',
    };
    const page: PageData = {
      ...samplePage,
      frontmatter: { title: 'Fallback', template: 'default' },
    };
    const html = renderPage(page, [page], configNoDefault);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Fallback</title>');
  });

  it('skips layout silently when layout file does not exist', () => {
    const page: PageData = {
      ...samplePage,
      frontmatter: {
        ...samplePage.frontmatter,
        layout: 'nonexistent_layout',
      },
    };
    const html = renderPage(page, [page], baseConfig);
    expect(html).toContain('<article');
  });

  it('excludes draft pages from pages list', () => {
    const draftPage: PageData = {
      ...samplePage,
      frontmatter: { ...samplePage.frontmatter, title: 'Draft', draft: true },
      isDraft: true,
    };
    const html = renderPage(samplePage, [samplePage, draftPage], baseConfig);
    expect(html).not.toContain('Draft');
  });

  afterAll(() => {
    fs.rmSync(baseConfig.outputDir, { recursive: true, force: true });
  });
});
