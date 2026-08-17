import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, parseMarkdown, splitFrontmatter, escapeHtml } from './index';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
}

describe('parseMarkdown', () => {
  it('renders markdown to HTML', () => {
    const { html } = parseMarkdown('# Hello\n\nWorld');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('World');
  });

  it('parses frontmatter (title, date, tags)', () => {
    const raw = `---
title: My Post
date: 2024-01-02
tags:
  - a
  - b
---
# Heading

Body
`;
    const { frontmatter, html } = parseMarkdown(raw);
    expect(frontmatter.title).toBe('My Post');
    expect(frontmatter.date).toBe('2024-01-02');
    expect(frontmatter.tags).toEqual(['a', 'b']);
    expect(html).toContain('<h1>Heading</h1>');
  });

  it('does not leak the frontmatter delimiters into HTML', () => {
    const raw = `---
title: No Leak
---
Some **bold** text
`;
    const { html } = parseMarkdown(raw);
    expect(html).not.toContain('---');
    expect(html).not.toContain('<hr>');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('handles files without frontmatter', () => {
    const { frontmatter, html } = parseMarkdown('Just text');
    expect(frontmatter).toEqual({});
    expect(html).toContain('Just text');
  });

  it('strips frontmatter even with leading whitespace', () => {
    const raw = `\n---\ntitle: Leading\n---\nbody`;
    const { frontmatter, html } = parseMarkdown(raw);
    expect(frontmatter.title).toBe('Leading');
    expect(html).not.toContain('---');
    expect(html).toContain('body');
  });
});

describe('splitFrontmatter', () => {
  it('returns empty data and full body when no frontmatter exists', () => {
    const { data, body } = splitFrontmatter('plain text');
    expect(data).toEqual({});
    expect(body).toBe('plain text');
  });
});

describe('escapeHtml', () => {
  it('escapes HTML special characters', () => {
    expect(escapeHtml('<a href="x">&\'')).toBe('&lt;a href=&quot;x&quot;&gt;&amp;&#39;');
  });
});

describe('buildSite', () => {
  it('generates index.html and one page per markdown file', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello World\ndate: 2024-01-01\ntags: [intro]\n---\n# Welcome\n\nHello there\n'
    );
    fs.writeFileSync(path.join(content, 'second.md'), '---\ntitle: Second\n---\nBody two\n');

    const site = buildSite({ contentDir: content, outputDir: output });

    expect(site.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(output, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(output, 'second.html'))).toBe(true);

    const helloHtml = fs.readFileSync(path.join(output, 'hello.html'), 'utf8');
    expect(helloHtml).toContain('<title>Hello World</title>');
    expect(helloHtml).toContain('<h1>Welcome</h1>');
    expect(helloHtml).toContain('Hello there');
    expect(helloHtml).not.toContain('---');

    const indexHtml = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
    expect(indexHtml).toContain('Hello World');
    expect(indexHtml).toContain('Second');
    expect(indexHtml).toContain('href="hello.html"');
    expect(indexHtml).toContain('href="second.html"');
  });

  it('orders pages by date descending', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(path.join(content, 'a.md'), '---\ntitle: A\ndate: 2024-01-01\n---\na\n');
    fs.writeFileSync(path.join(content, 'b.md'), '---\ntitle: B\ndate: 2024-03-01\n---\nb\n');

    const site = buildSite({ contentDir: content, outputDir: output });
    expect(site.pages.map((p) => p.slug)).toEqual(['b', 'a']);
  });

  it('supports nested directories', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const sub = path.join(content, 'nested');
    fs.mkdirSync(sub);
    fs.writeFileSync(path.join(sub, 'deep.md'), '---\ntitle: Deep\n---\nDeep body\n');

    const site = buildSite({ contentDir: content, outputDir: output });
    expect(site.pages).toHaveLength(1);
    expect(site.pages[0].slug).toBe('nested/deep');
    expect(fs.existsSync(path.join(output, 'nested', 'deep.html'))).toBe(true);
  });

  it('ignores non-markdown files', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(path.join(content, 'notes.txt'), 'not markdown');
    fs.writeFileSync(path.join(content, 'post.md'), '---\ntitle: Post\n---\nhi\n');

    const site = buildSite({ contentDir: content, outputDir: output });
    expect(site.pages).toHaveLength(1);
  });

  it('handles an empty content directory', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const site = buildSite({ contentDir: content, outputDir: output });
    expect(site.pages).toHaveLength(0);
    expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
  });

  it('defaults title from slug when frontmatter title is missing', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(path.join(content, 'my-post.md'), '---\ndate: 2024-01-01\n---\nbody\n');

    const site = buildSite({ contentDir: content, outputDir: output });
    expect(site.pages[0].title).toBe('My Post');
  });
});
