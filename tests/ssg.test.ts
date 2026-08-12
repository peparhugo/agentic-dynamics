import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  build,
  parseMarkdown,
  readPages,
  renderIndex,
  renderPage,
  sortPages,
} from '../src/ssg';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('parseMarkdown', () => {
  it('reads frontmatter fields delimited by HTML comments', () => {
    const raw = `<!--
title: My First Post
date: 2024-01-15
tags:
  - meta
  - tutorial
-->

# Heading

Some **bold** text.
`;

    const page = parseMarkdown(raw, 'my-first-post');

    expect(page.slug).toBe('my-first-post');
    expect(page.title).toBe('My First Post');
    expect(page.date).toBe('2024-01-15');
    expect(page.tags).toEqual(['meta', 'tutorial']);
    expect(page.html).toContain('<h1>Heading</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
  });

  it('normalizes YAML timestamps to a YYYY-MM-DD date string', () => {
    const raw = `<!--
title: Dated
date: 2024-03-09
-->
Body
`;
    const page = parseMarkdown(raw, 'dated');
    expect(page.date).toBe('2024-03-09');
  });

  it('falls back to the slug when no title is given', () => {
    const page = parseMarkdown('# Just a heading', 'untitled-page');
    expect(page.title).toBe('untitled-page');
    expect(page.tags).toEqual([]);
    expect(page.date).toBeUndefined();
  });

  it('parses markdown with no frontmatter block at all', () => {
    const page = parseMarkdown('# Plain\n\nHello world', 'plain');
    expect(page.title).toBe('plain');
    expect(page.html).toContain('<h1>Plain</h1>');
    expect(page.html).toContain('Hello world');
  });

  it('parses inline flow-sequence tags inside a multiline block', () => {
    const raw = `<!--
title: T
tags: [one, two]
-->
Body`;
    const page = parseMarkdown(raw, 't');
    expect(page.title).toBe('T');
    expect(page.tags).toEqual(['one', 'two']);
  });
});

describe('readPages', () => {
  it('reads every .md file from the content directory', () => {
    const dir = makeTempDir();
    try {
      fs.writeFileSync(path.join(dir, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      fs.writeFileSync(path.join(dir, 'b.md'), '<!--\ntitle: B\n-->\n# B');
      fs.writeFileSync(path.join(dir, 'not-markdown.txt'), 'nope');
      fs.writeFileSync(path.join(dir, 'README.MD'), '<!--\ntitle: Caps\n-->\n# Caps');

      const pages = readPages(dir);
      expect(pages.map((p) => p.slug).sort()).toEqual(['README', 'a', 'b']);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('throws when the content directory does not exist', () => {
    expect(() => readPages(path.join(os.tmpdir(), 'does-not-exist-xyz'))).toThrow(
      /Content directory not found/
    );
  });
});

describe('sortPages', () => {
  it('sorts dated pages newest first and keeps undated pages stable', () => {
    const pages = [
      { slug: 'old', date: '2020-01-01' },
      { slug: 'new', date: '2024-06-01' },
      { slug: 'undated' },
    ] as Array<ReturnType<typeof parseMarkdown>>;

    const sorted = sortPages(pages);
    expect(sorted.map((p) => p.slug)).toEqual(['new', 'old', 'undated']);
  });
});

describe('render', () => {
  it('renderPage produces a standalone HTML document', () => {
    const page = parseMarkdown('<!--\ntitle: Hi\n-->\n# Hi', 'hi');
    const html = renderPage(page);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Hi</title>');
    expect(html).toContain('<h1>Hi</h1>');
  });

  it('escapes titles coming from frontmatter', () => {
    const page = parseMarkdown('<!--\ntitle: A <script>\n-->\nbody', 'x');
    const html = renderPage(page);
    expect(html).toContain('A &lt;script&gt;');
    expect(html).not.toContain('<script>');
  });

  it('renderIndex links to every page', () => {
    const a = parseMarkdown('<!--\ntitle: Alpha\n-->\n# A', 'alpha');
    const b = parseMarkdown('<!--\ntitle: Beta\ndate: 2024-01-01\n-->\n# B', 'beta');
    const html = renderIndex([a, b]);
    expect(html).toContain('<a href="alpha.html">Alpha</a>');
    expect(html).toContain('<a href="beta.html">Beta</a>');
  });
});

describe('build', () => {
  it('generates per-page HTML files plus an index.html in the output directory', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    try {
      fs.writeFileSync(
        path.join(content, 'post.md'),
        `<!--
title: Post One
date: 2024-05-10
tags: [news]
-->

# Post One body
`
      );
      fs.writeFileSync(path.join(content, 'other.md'), '<!--\ntitle: Other\n-->\n# Other');

      const pages = build(content, output);

      expect(pages.map((p) => p.slug)).toEqual(['post', 'other']);

      const postHtml = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
      expect(postHtml).toContain('<title>Post One</title>');
      expect(postHtml).toContain('<h1>Post One body</h1>');

      const otherHtml = fs.readFileSync(path.join(output, 'other.html'), 'utf8');
      expect(otherHtml).toContain('<title>Other</title>');

      const indexHtml = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
      expect(indexHtml).toContain('<a href="post.html">Post One</a>');
      expect(indexHtml).toContain('<a href="other.html">Other</a>');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
    }
  });

  it('creates the output directory when it does not exist', () => {
    const content = makeTempDir();
    const base = makeTempDir();
    const output = path.join(base, 'nested', 'dist');
    try {
      fs.writeFileSync(path.join(content, 'p.md'), '<!--\ntitle: P\n-->\n# P');
      build(content, output);
      expect(fs.existsSync(path.join(output, 'p.html'))).toBe(true);
      expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(base, { recursive: true, force: true });
    }
  });

  it('uses default content and output directories when called with no args', () => {
    const cwd = process.cwd();
    const content = makeTempDir();
    try {
      fs.mkdirSync(path.join(content, 'content'));
      fs.mkdirSync(path.join(content, 'dist'));
      fs.writeFileSync(path.join(content, 'content', 'hello.md'), '<!--\ntitle: Hello\n-->\n# Hello');
      process.chdir(content);

      const pages = build();
      expect(pages).toHaveLength(1);
      expect(fs.existsSync(path.join(content, 'dist', 'hello.html'))).toBe(true);
      expect(fs.existsSync(path.join(content, 'dist', 'index.html'))).toBe(true);
    } finally {
      process.chdir(cwd);
      fs.rmSync(content, { recursive: true, force: true });
    }
  });
});
