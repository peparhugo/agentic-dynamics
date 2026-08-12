import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  buildSite,
  collectMarkdownFiles,
  slugFor,
} from '../src/build';

describe('buildSite', () => {
  let tmp: string;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(() => {
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  function writeContent(relPath: string, content: string): string {
    const full = path.join(tmp, 'content', relPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  it('generates an HTML file for every markdown page', async () => {
    writeContent('hello.md', '---\ntitle: Hello World\ndate: 2024-01-01\ntags:\n  - intro\n---\n\n# Hi there\n\nWelcome!');
    writeContent('about.md', '# About us');

    const outputDir = path.join(tmp, 'dist');
    const pages = await buildSite({ contentDir: path.join(tmp, 'content'), outputDir });

    expect(pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);

    const hello = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(hello).toContain('<h1>Hello World</h1>');
    expect(hello).toContain('<h1>Hi there</h1>');
    expect(hello).toContain('<p>Welcome!</p>');
    expect(hello).toContain('2024-01-01');
    expect(hello).toContain('intro');
  });

  it('generates an index.html listing all pages', async () => {
    writeContent('a.md', '---\ntitle: Page A\ndate: 2024-01-02\n---\n\n# A');
    writeContent('b.md', '---\ntitle: Page B\ndate: 2024-01-01\n---\n\n# B');

    const outputDir = path.join(tmp, 'dist');
    await buildSite({ contentDir: path.join(tmp, 'content'), outputDir });

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<a href="a.html">Page A</a>');
    expect(index).toContain('<a href="b.html">Page B</a>');
  });

  it('sorts index entries by date, newest first', async () => {
    writeContent('older.md', '---\ntitle: Older\ndate: 2020-01-01\n---\n\n# Older');
    writeContent('newer.md', '---\ntitle: Newer\ndate: 2024-05-05\n---\n\n# Newer');

    const outputDir = path.join(tmp, 'dist');
    await buildSite({ contentDir: path.join(tmp, 'content'), outputDir });

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    const newerPos = index.indexOf('Newer');
    const olderPos = index.indexOf('Older');
    expect(newerPos).toBeGreaterThan(-1);
    expect(olderPos).toBeGreaterThan(-1);
    expect(newerPos).toBeLessThan(olderPos);
  });

  it('supports markdown files in nested directories', async () => {
    writeContent('blog/post.md', '---\ntitle: A Post\ndate: 2024-01-01\n---\n\n# Post body');

    const outputDir = path.join(tmp, 'dist');
    const pages = await buildSite({ contentDir: path.join(tmp, 'content'), outputDir });

    expect(pages[0].slug).toBe('blog/post');
    expect(fs.existsSync(path.join(outputDir, 'blog/post.html'))).toBe(true);
    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<a href="blog/post.html">A Post</a>');
  });

  it('handles a missing content directory gracefully', async () => {
    const outputDir = path.join(tmp, 'dist');
    const pages = await buildSite({ contentDir: path.join(tmp, 'does-not-exist'), outputDir });

    expect(pages).toHaveLength(0);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('No pages found.');
  });

  it('uses the configured site title', async () => {
    writeContent('page.md', '# Body');

    const outputDir = path.join(tmp, 'dist');
    await buildSite({ contentDir: path.join(tmp, 'content'), outputDir, siteTitle: 'My Blog' });

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<title>My Blog</title>');
    expect(index).toContain('<h1>My Blog</h1>');
  });

  it('escapes frontmatter title in generated HTML', async () => {
    writeContent('page.md', '---\ntitle: "A & B <tag>"\n---\n\n# Body');

    const outputDir = path.join(tmp, 'dist');
    await buildSite({ contentDir: path.join(tmp, 'content'), outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf8');
    expect(html).toContain('<title>A &amp; B &lt;tag&gt;</title>');
    expect(html).not.toContain('<title>A & B <tag></title>');
  });
});

describe('collectMarkdownFiles', () => {
  it('returns an empty list for a missing directory', () => {
    expect(collectMarkdownFiles('/path/that/does/not/exist')).toEqual([]);
  });

  it('only collects markdown files recursively', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
    try {
      const contentDir = path.join(tmp, 'content');
      fs.mkdirSync(path.join(contentDir, 'sub'), { recursive: true });
      fs.writeFileSync(path.join(contentDir, 'a.md'), '# a');
      fs.writeFileSync(path.join(contentDir, 'b.markdown'), '# b');
      fs.writeFileSync(path.join(contentDir, 'notes.txt'), 'not markdown');
      fs.writeFileSync(path.join(contentDir, 'sub', 'c.md'), '# c');

      const files = collectMarkdownFiles(contentDir);
      expect(files).toHaveLength(3);
      expect(files.some((f) => f.endsWith('a.md'))).toBe(true);
      expect(files.some((f) => f.endsWith('b.markdown'))).toBe(true);
      expect(files.some((f) => f.endsWith('c.md'))).toBe(true);
      expect(files.some((f) => f.endsWith('notes.txt'))).toBe(false);
    } finally {
      fs.rmSync(tmp, { recursive: true, force: true });
    }
  });
});

describe('slugFor', () => {
  it('converts a file path to a slug relative to the content dir', () => {
    expect(slugFor('/site/content/about.md', '/site/content')).toBe('about');
    expect(slugFor('/site/content/blog/post.markdown', '/site/content')).toBe('blog/post');
  });
});
