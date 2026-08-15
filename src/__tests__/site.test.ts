import fs from 'fs';
import os from 'os';
import path from 'path';

import { escapeHtml, pageTitle, renderIndex, renderPage } from '../render';
import { buildSite, listMarkdownFiles, loadPages, readPage, slugify } from '../site';
import type { Page } from '../types';

const SAMPLE_MD = `---
title: Sample
date: 2026-05-01
tags: demo, test
---

# Heading

Some <b>body</b> content.
`;

describe('slugify', () => {
  it('strips the file extension', () => {
    expect(slugify('hello-world.md')).toBe('hello-world');
    expect(slugify('guide.md')).toBe('guide');
  });
});

describe('listMarkdownFiles', () => {
  it('returns only Markdown files', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
    fs.writeFileSync(path.join(dir, 'a.md'), '# a');
    fs.writeFileSync(path.join(dir, 'b.MD'), '# b');
    fs.writeFileSync(path.join(dir, 'notes.txt'), 'hi');

    const files = listMarkdownFiles(dir);
    expect(files).toEqual(['a.md', 'b.MD']);
  });

  it('returns an empty list for a missing directory', () => {
    expect(listMarkdownFiles(path.join(os.tmpdir(), 'does-not-exist-ssg'))).toEqual([]);
  });
});

describe('loadPages', () => {
  it('reads, parses and sorts Markdown files into pages', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
    fs.writeFileSync(path.join(dir, 'b.md'), SAMPLE_MD);
    fs.writeFileSync(path.join(dir, 'a.md'), '---\ntitle: Alpha\n---\nContent A.');

    const pages = loadPages(dir);
    expect(pages).toHaveLength(2);
    expect(pages[0].slug).toBe('a');
    expect(pages[1].slug).toBe('b');
    expect(pages[1].title).toBe('Sample');
    expect(pages[1].date).toBe('2026-05-01');
    expect(pages[1].tags).toEqual(['demo', 'test']);
    expect(pages[1].outputName).toBe('b.html');
    expect(pages[1].html).toContain('<h1');
  });
});

describe('readPage', () => {
  it('falls back to the slug when no title is provided', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
    fs.writeFileSync(path.join(dir, 'untitled.md'), '# Body');
    const page = readPage('untitled.md', dir);
    expect(page.title).toBe('untitled');
  });
});

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-content-'));
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-dist-'));
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  // Point at a non-existent templates directory so these tests exercise the
  // built-in renderers regardless of whether ./templates exists in the repo.
  const missingTemplatesDir = () => path.join(outputDir, 'missing-templates');

  it('writes a page html file and an index.html', () => {
    fs.writeFileSync(path.join(contentDir, 'first.md'), SAMPLE_MD);

    const pages = buildSite({ contentDir, outputDir, templatesDir: missingTemplatesDir() });

    expect(pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const pageHtml = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf8');
    expect(pageHtml).toContain('<h1>Sample</h1>');
    expect(pageHtml).toContain('>2026-05-01</p>');
    expect(pageHtml).toContain('class="tag">demo');
    expect(pageHtml).toContain('Some <b>body</b> content.');

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('href="first.html"');
    expect(indexHtml).toContain('Sample');
  });

  it('escapes frontmatter-derived values in generated HTML', () => {
    fs.writeFileSync(
      path.join(contentDir, 'x.md'),
      '---\ntitle: <script>alert(1)</script>\n---\nBody'
    );

    buildSite({ contentDir, outputDir, templatesDir: missingTemplatesDir() });

    const pageHtml = fs.readFileSync(path.join(outputDir, 'x.html'), 'utf8');
    expect(pageHtml).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(pageHtml).not.toContain('<script>alert(1)</script>');
  });

  it('writes one file per page plus the index', () => {
    fs.writeFileSync(path.join(contentDir, 'one.md'), SAMPLE_MD);
    fs.writeFileSync(path.join(contentDir, 'two.md'), '---\ntitle: Two\n---\nBody');

    buildSite({ contentDir, outputDir, templatesDir: missingTemplatesDir() });

    const files = fs.readdirSync(outputDir).sort();
    expect(files).toEqual(['index.html', 'one.html', 'two.html']);
  });

  it('creates the output directory when missing', () => {
    const nested = path.join(outputDir, 'missing', 'site');
    fs.writeFileSync(path.join(contentDir, 'one.md'), SAMPLE_MD);

    buildSite({ contentDir, outputDir: nested, templatesDir: missingTemplatesDir() });
    expect(fs.existsSync(path.join(nested, 'index.html'))).toBe(true);
  });

  it('handles an empty content directory', () => {
    const pages = buildSite({ contentDir, outputDir, templatesDir: missingTemplatesDir() });
    expect(pages).toHaveLength(0);
    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('No pages yet.');
  });
});

describe('render helpers', () => {
  it('escapeHtml escapes HTML-sensitive characters', () => {
    expect(escapeHtml('<b>&"\'>')).toBe('&lt;b&gt;&amp;&quot;&#39;&gt;');
  });

  it('pageTitle uses frontmatter title or a fallback', () => {
    expect(pageTitle({ title: 'T' }, 'fallback')).toBe('T');
    expect(pageTitle({ title: '  ' }, 'fallback')).toBe('fallback');
    expect(pageTitle({}, 'fallback')).toBe('fallback');
  });

  it('renderPage includes the page content and index link', () => {
    const page: Page = {
      slug: 'x',
      sourcePath: 'x.md',
      outputName: 'x.html',
      title: 'X',
      date: '2026-01-01',
      tags: ['t'],
      html: '<p>hello</p>',
      content: 'hello',
      raw: 'hello',
      data: { title: 'X', date: '2026-01-01', tags: ['t'] },
    };
    const html = renderPage(page);
    expect(html).toContain('<title>X</title>');
    expect(html).toContain('<p>hello</p>');
    expect(html).toContain('href="index.html"');
  });

  it('renderIndex lists all pages with links', () => {
    const pages: Page[] = [
      {
        slug: 'a',
        sourcePath: 'a.md',
        outputName: 'a.html',
        title: 'A',
        tags: [],
        html: '',
        content: '',
        raw: '',
        data: { title: 'A' },
      },
      {
        slug: 'b',
        sourcePath: 'b.md',
        outputName: 'b.html',
        title: 'B',
        date: '2026-01-01',
        tags: ['x', 'y'],
        html: '',
        content: '',
        raw: '',
        data: { title: 'B', date: '2026-01-01', tags: ['x', 'y'] },
      },
    ];
    const html = renderIndex(pages);
    expect(html).toContain('href="a.html">A</a>');
    expect(html).toContain('href="b.html">B</a>');
    expect(html).toContain('>2026-01-01</span>');
  });
});
