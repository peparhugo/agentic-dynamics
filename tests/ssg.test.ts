import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  parseMarkdown,
  markdownToHtml,
  toDate,
  buildPage,
  sortByDate,
  loadPages,
  build,
  escapeHtml,
} from '../src';

describe('parseMarkdown', () => {
  it('extracts title, date and tags from frontmatter', () => {
    const raw = `---
title: Hello World
date: 2024-01-15
tags:
  - a
  - b
---
# Body
`;
    const { data, content } = parseMarkdown(raw);
    expect(data.title).toBe('Hello World');
    expect(data.date).toBeInstanceOf(Date);
    expect((data.date as Date).toISOString().slice(0, 10)).toBe('2024-01-15');
    expect(data.tags).toEqual(['a', 'b']);
    expect(content.trim()).toBe('# Body');
  });
});

describe('markdownToHtml', () => {
  it('converts markdown to html', () => {
    expect(markdownToHtml('# Hi').trim()).toContain('<h1');
    expect(markdownToHtml('**bold**').trim()).toContain('<strong>bold</strong>');
  });
});

describe('toDate', () => {
  it('passes through Date objects', () => {
    const d = new Date('2020-05-05');
    expect(toDate(d).getTime()).toBe(d.getTime());
  });
  it('parses strings', () => {
    expect(toDate('2020-05-05').getTime()).toBe(new Date('2020-05-05').getTime());
  });
  it('falls back to epoch for invalid dates', () => {
    expect(toDate(undefined).getTime()).toBe(0);
    expect(toDate('not-a-date').getTime()).toBe(0);
  });
});

describe('buildPage', () => {
  it('builds a page with parsed frontmatter and html', () => {
    const raw = `---
title: T
date: 2024-06-01
tags: [x]
---
# Hi
`;
    const page = buildPage('my-post', raw);
    expect(page.slug).toBe('my-post');
    expect(page.title).toBe('T');
    expect(page.date).toBeInstanceOf(Date);
    expect(page.tags).toEqual(['x']);
    expect(page.html).toContain('<h1');
  });
});

describe('sortByDate', () => {
  it('sorts pages newest first', () => {
    const pages = [
      buildPage('old', '---\ntitle: Old\ndate: 2020-01-01\n---\n'),
      buildPage('new', '---\ntitle: New\ndate: 2023-01-01\n---\n'),
      buildPage('none', '---\ntitle: None\n---\n'),
    ];
    const sorted = sortByDate(pages);
    expect(sorted.map((p) => p.slug)).toEqual(['new', 'old', 'none']);
  });
});

describe('escapeHtml', () => {
  it('escapes html characters', () => {
    expect(escapeHtml('<a href="x">&')).toBe('&lt;a href=&quot;x&quot;&gt;&amp;');
  });
});

describe('loadPages', () => {
  it('loads and sorts markdown files from a directory', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-load-'));
    fs.writeFileSync(path.join(dir, 'a.md'), '---\ntitle: A\ndate: 2024-01-01\n---\n# A\n');
    fs.writeFileSync(path.join(dir, 'b.md'), '---\ntitle: B\ndate: 2024-02-01\n---\n# B\n');
    fs.writeFileSync(path.join(dir, 'skip.txt'), 'not markdown');
    const pages = loadPages(dir);
    expect(pages.map((p) => p.slug)).toEqual(['b', 'a']);
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('throws when the directory is missing', () => {
    expect(() => loadPages('/does/not/exist')).toThrow();
  });
});

describe('build', () => {
  it('generates index.html and page files sorted by date', () => {
    const content = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-content-'));
    const out = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-out-'));
    fs.writeFileSync(
      path.join(content, 'first.md'),
      '---\ntitle: First\ndate: 2024-01-10\n---\n# First\n'
    );
    fs.writeFileSync(
      path.join(content, 'second.md'),
      '---\ntitle: Second\ndate: 2024-03-01\n---\n# Second\n'
    );

    const pages = build({ contentDir: content, outputDir: out });

    expect(pages.map((p) => p.slug)).toEqual(['second', 'first']);

    const index = fs.readFileSync(path.join(out, 'index.html'), 'utf-8');
    expect(index).toContain('Second');
    expect(index).toContain('First');
    expect(index.indexOf('Second')).toBeLessThan(index.indexOf('First'));

    expect(fs.existsSync(path.join(out, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(out, 'second.html'))).toBe(true);
    const pageHtml = fs.readFileSync(path.join(out, 'second.html'), 'utf-8');
    expect(pageHtml).toContain('<h1>Second</h1>');

    fs.rmSync(content, { recursive: true, force: true });
    fs.rmSync(out, { recursive: true, force: true });
  });
});
