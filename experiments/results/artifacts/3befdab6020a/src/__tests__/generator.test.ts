import fs from 'fs';
import path from 'path';
import os from 'os';
import { Page } from '../types';
import { generateSite } from '../generator';

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

describe('generateSite', () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-gen-test-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('creates the output directory if it does not exist', () => {
    const outDir = path.join(tmpDir, 'nested', 'output');
    generateSite([makePage()], outDir);
    expect(fs.existsSync(outDir)).toBe(true);
  });

  it('generates an index.html file', () => {
    generateSite([makePage()], tmpDir);

    const indexPath = path.join(tmpDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const html = fs.readFileSync(indexPath, 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Site Index</title>');
    expect(html).toContain('<h1>Site Index</h1>');
  });

  it('generates a page HTML file', () => {
    generateSite([makePage()], tmpDir);

    const pagePath = path.join(tmpDir, 'test-page.html');
    expect(fs.existsSync(pagePath)).toBe(true);

    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Test Page</title>');
    expect(html).toContain('<h1>Test Page</h1>');
    expect(html).toContain('<p>Some markdown content</p>');
  });

  it('includes date in page HTML when present', () => {
    generateSite([makePage({ frontmatter: { title: 'Dated', date: '2024-01-15', tags: [] } })], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).toContain('Date: 2024-01-15');
  });

  it('omits date when empty', () => {
    generateSite([makePage({ frontmatter: { title: 'No Date', date: '', tags: [] } })], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).not.toContain('Date:');
  });

  it('includes tags in page HTML when present', () => {
    generateSite([makePage()], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).toContain('Tags: typescript, testing');
  });

  it('omits tags section when empty', () => {
    generateSite([makePage({ frontmatter: { title: 'No Tags', date: '', tags: [] } })], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).not.toContain('Tags:');
  });

  it('index links to all pages', () => {
    const pages = [
      makePage({ slug: 'alpha', frontmatter: { title: 'Alpha', date: '', tags: [] } }),
      makePage({ slug: 'beta', frontmatter: { title: 'Beta', date: '', tags: [] } }),
    ];

    generateSite(pages, tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'index.html'), 'utf-8');
    expect(html).toContain('<a href="alpha.html">Alpha</a>');
    expect(html).toContain('<a href="beta.html">Beta</a>');
  });

  it('pages link back to index', () => {
    generateSite([makePage()], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).toContain('<a href="index.html">Back to index</a>');
  });

  it('generates valid HTML structure', () => {
    generateSite([makePage()], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<html lang="en">');
    expect(html).toContain('<head>');
    expect(html).toContain('<meta charset="UTF-8">');
    expect(html).toContain('<body>');
  });

  it('escapes HTML in titles', () => {
    generateSite([makePage({ frontmatter: { title: 'A <script>alert("xss")</script>', date: '', tags: [] } })], tmpDir);

    const html = fs.readFileSync(path.join(tmpDir, 'test-page.html'), 'utf-8');
    expect(html).toContain('A &lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
    expect(html).not.toContain('<script>alert');
  });

  it('generates multiple pages', () => {
    const pages = [
      makePage({ slug: 'page1', frontmatter: { title: 'Page 1', date: '', tags: [] } }),
      makePage({ slug: 'page2', frontmatter: { title: 'Page 2', date: '', tags: [] } }),
    ];

    generateSite(pages, tmpDir);
    expect(fs.existsSync(path.join(tmpDir, 'page1.html'))).toBe(true);
    expect(fs.existsSync(path.join(tmpDir, 'page2.html'))).toBe(true);
    expect(fs.existsSync(path.join(tmpDir, 'index.html'))).toBe(true);
  });
});
