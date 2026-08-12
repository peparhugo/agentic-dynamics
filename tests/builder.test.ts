import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  buildSite,
  renderIndex,
  renderPage,
  sortPages,
} from '../src/builder';
import { Page } from '../src/types';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

function writeContent(contentDir: string, name: string, body: string): string {
  const file = path.join(contentDir, name);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, body, 'utf8');
  return file;
}

describe('buildSite', () => {
  it('generates index.html and per-page html files', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    writeContent(
      contentDir,
      'hello.md',
      `---
title: Hello
date: 2026-01-15
tags: [intro]
---

# Hello

Welcome with **bold** text.
`,
    );
    writeContent(
      contentDir,
      'about.md',
      `---
title: About
date: 2026-02-01
---
## About me
`,
    );

    const pages = buildSite(contentDir, outputDir);

    expect(pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('href="about.html"');
    expect(index).toContain('href="hello.html"');

    const hello = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(hello).toContain('<h1>Hello</h1>');
    expect(hello).toContain('<strong>');
  });

  it('sorts pages by date descending in the index', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    writeContent(contentDir, 'old.md', '---\ntitle: Old\ndate: 2020-01-01\n---\nold');
    writeContent(contentDir, 'new.md', '---\ntitle: New\ndate: 2026-01-01\n---\nnew');

    buildSite(contentDir, outputDir);
    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index.indexOf('href="new.html"')).toBeLessThan(
      index.indexOf('href="old.html"'),
    );
  });

  it('handles a missing content directory', () => {
    const root = makeTempDir();
    const outputDir = path.join(root, 'dist');
    const pages = buildSite(path.join(root, 'does-not-exist'), outputDir);
    expect(pages).toEqual([]);
    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<ul>');
  });

  it('recurses into subdirectories', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeContent(contentDir, 'nested/deep.md', '---\ntitle: Deep\n---\n# Deep');
    const pages = buildSite(contentDir, outputDir);
    expect(pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'deep.html'))).toBe(true);
  });
});

describe('renderPage', () => {
  it('includes tags and a link back to the index', () => {
    const page: Page = {
      slug: 'test',
      title: 'Test <Title>',
      date: '2026-01-01',
      tags: ['a', 'b'],
      content: '<p>Body</p>',
    };
    const html = renderPage(page);
    expect(html).toContain('Test &lt;Title&gt;');
    expect(html).toContain('<span class="tag">a</span>');
    expect(html).toContain('href="index.html"');
    expect(html).toContain('<time datetime="2026-01-01">');
  });
});

describe('renderIndex', () => {
  it('lists pages with links, dates and tags', () => {
    const pages: Page[] = [
      {
        slug: 'a',
        title: 'A Page',
        date: '2026-01-01',
        tags: ['x'],
        content: '',
      },
      { slug: 'b', title: 'B Page', tags: [], content: '' },
    ];
    const html = renderIndex(pages);
    expect(html).toContain('href="a.html">A Page</a>');
    expect(html).toContain('#x');
    expect(html).toContain('href="b.html">B Page</a>');
  });
});

describe('sortPages', () => {
  it('sorts by date descending', () => {
    const a: Page = { slug: 'a', title: 'A', date: '2020-01-01', tags: [], content: '' };
    const b: Page = { slug: 'b', title: 'B', date: '2026-01-01', tags: [], content: '' };
    const c: Page = { slug: 'c', title: 'C', tags: [], content: '' };
    expect(sortPages([a, c, b]).map((p) => p.slug)).toEqual(['b', 'a', 'c']);
  });
});
