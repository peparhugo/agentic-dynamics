import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, renderIndex, renderPage } from '../src/generator';
import type { Page } from '../src/types';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), content);
  }
}

describe('renderPage', () => {
  it('renders a full HTML page with title and content', () => {
    const page: Page = {
      slug: 'hello',
      title: 'Hello',
      date: '2024-01-01',
      tags: ['intro'],
      contentHtml: '<p>World</p>',
      content: '# Hello',
    };
    const html = renderPage(page);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<p>World</p>');
    expect(html).toContain('2024-01-01');
    expect(html).toContain('<li>intro</li>');
  });

  it('escapes special characters in metadata', () => {
    const page: Page = {
      slug: 'x',
      title: '<script>alert("x")</script>',
      contentHtml: '',
      content: '',
    };
    const html = renderPage(page);
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>');
  });
});

describe('renderIndex', () => {
  it('lists all pages as links to their html files', () => {
    const pages: Page[] = [
      { slug: 'a', title: 'Page A', contentHtml: '', content: '' },
      { slug: 'b', title: 'Page B', date: '2024-02-02', contentHtml: '', content: '' },
    ];
    const html = renderIndex(pages);
    expect(html).toContain('<a href="a.html">Page A</a>');
    expect(html).toContain('<a href="b.html">Page B</a>');
    expect(html).toContain('2024-02-02');
  });
});

describe('buildSite', () => {
  it('throws when the content directory does not exist', () => {
    const tmp = makeTempDir('ssg-missing-');
    expect(() =>
      buildSite({ contentDir: path.join(tmp, 'nope'), outputDir: path.join(tmp, 'dist') })
    ).toThrow(/Content directory does not exist/);
  });

  it('generates a page per markdown file plus an index', () => {
    const tmp = makeTempDir('ssg-build-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    writeContent(contentDir, {
      'first.md': '---\ntitle: First\ndate: 2024-03-01\ntags: [news]\n---\n\n# First post\n\nSome *body*.',
      'second.md': '# Second post\n\nPlain markdown.',
      'ignored.txt': 'not markdown',
    });

    const pages = buildSite({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'ignored.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const first = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf8');
    expect(first).toContain('<title>First</title>');
    expect(first).toContain('Some <em>body</em>');
    expect(first).toContain('2024-03-01');

    const second = fs.readFileSync(path.join(outputDir, 'second.html'), 'utf8');
    expect(second).toContain('<title>second</title>');

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<a href="first.html">First</a>');
    expect(index).toContain('<a href="second.html">second</a>');

    expect(pages.map((p) => p.slug).sort()).toEqual(['first', 'second']);
  });

  it('re-creates the output directory when it already exists', () => {
    const tmp = makeTempDir('ssg-rebuild-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    writeContent(contentDir, { 'a.md': '# A' });

    buildSite({ contentDir, outputDir });
    buildSite({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('handles an empty content directory', () => {
    const tmp = makeTempDir('ssg-empty-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    fs.mkdirSync(contentDir, { recursive: true });

    const pages = buildSite({ contentDir, outputDir });
    expect(pages).toEqual([]);
    expect(fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8')).toContain('<ul>');
  });
});
