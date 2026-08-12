import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseMarkdown, slugify } from '../parse';
import { buildSite } from '../build';
import { renderIndex, renderPage, escapeHtml } from '../template';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('slugify', () => {
  it('lowercases and kebab-cases a filename', () => {
    expect(slugify('My First Post.md')).toBe('my-first-post');
  });

  it('strips the extension', () => {
    expect(slugify('about.markdown')).toBe('about');
  });

  it('handles slugs with numbers', () => {
    expect(slugify('part-1.md')).toBe('part-1');
  });
});

describe('parseMarkdown', () => {
  it('parses frontmatter title, date, and tags', () => {
    const page = parseMarkdown(
      `---
title: Hello World
date: 2024-01-15
tags: [intro, welcome]
---

# Heading

Some **bold** text.
`,
      'hello-world.md',
    );

    expect(page.title).toBe('Hello World');
    expect(page.date).toBe('2024-01-15');
    expect(page.tags).toEqual(['intro', 'welcome']);
    expect(page.slug).toBe('hello-world');
    expect(page.contentHtml).toContain('<h1>Heading</h1>');
    expect(page.contentHtml).toContain('<strong>bold</strong>');
  });

  it('parses comma-separated tags from a string', () => {
    const page = parseMarkdown(
      `---
title: Tags
tags: one, two, three
---

Body
`,
      'tags.md',
    );

    expect(page.tags).toEqual(['one', 'two', 'three']);
  });

  it('falls back to slug as title when frontmatter is missing', () => {
    const page = parseMarkdown('# Just a heading', 'no-title.md');
    expect(page.title).toBe('no-title');
    expect(page.tags).toEqual([]);
    expect(page.date).toBeUndefined();
    expect(page.contentHtml).toContain('<h1>Just a heading</h1>');
  });
});

describe('renderPage', () => {
  it('renders a full HTML document with escaped title', () => {
    const page = {
      slug: 'post',
      title: 'A <script> Title',
      date: '2024-01-01',
      tags: ['x'],
      contentHtml: '<p>Body</p>',
      source: 'post.md',
    };
    const html = renderPage(page);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('<h1>A &lt;script&gt; Title</h1>');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('index.html');
  });
});

describe('renderIndex', () => {
  it('lists pages with links sorted by date descending', () => {
    const pages = [
      {
        slug: 'old',
        title: 'Old',
        date: '2023-01-01',
        tags: [],
        contentHtml: '',
        source: 'old.md',
      },
      {
        slug: 'new',
        title: 'New',
        date: '2024-01-01',
        tags: [],
        contentHtml: '',
        source: 'new.md',
      },
    ];
    const html = renderIndex(pages);
    const newIndex = html.indexOf('new.html');
    const oldIndex = html.indexOf('old.html');
    expect(newIndex).toBeGreaterThan(-1);
    expect(oldIndex).toBeGreaterThan(-1);
    expect(newIndex).toBeLessThan(oldIndex);
  });
});

describe('escapeHtml', () => {
  it('escapes special characters', () => {
    expect(escapeHtml(`<a href="x">&'`)).toBe('&lt;a href=&quot;x&quot;&gt;&amp;&#39;');
  });
});

describe('buildSite', () => {
  it('generates index.html and one HTML file per page', () => {
    const contentDir = path.join(makeTempDir(), 'content');
    const outputDir = path.join(makeTempDir(), 'dist');
    fs.mkdirSync(contentDir, { recursive: true });

    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      `---
title: First
date: 2024-02-01
tags: [one]
---

# First post
`,
      'utf8',
    );

    const nestedDir = path.join(contentDir, 'nested');
    fs.mkdirSync(nestedDir, { recursive: true });
    fs.writeFileSync(
      path.join(nestedDir, 'second.md'),
      `---
title: Second
date: 2024-01-01
---

Second body
`,
      'utf8',
    );

    const result = buildSite(contentDir, outputDir);

    expect(result.pages).toHaveLength(2);
    expect(result.pages.map((p) => p.slug).sort()).toEqual(['first', 'second']);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('first.html');
    expect(index).toContain('second.html');
    expect(index).toContain('First');

    const page = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf8');
    expect(page).toContain('<h1>First</h1>');
    expect(page).toContain('First post');
  });

  it('handles an empty content directory', () => {
    const contentDir = path.join(makeTempDir(), 'empty');
    const outputDir = path.join(makeTempDir(), 'dist');
    fs.mkdirSync(contentDir, { recursive: true });

    const result = buildSite(contentDir, outputDir);
    expect(result.pages).toHaveLength(0);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });
});
