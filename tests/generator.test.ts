import { mkdtempSync, writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { buildSite, loadPages, renderIndex, renderPage, toSlug } from '../src/generator';

function makeTempDir(): string {
  return mkdtempSync(path.join(tmpdir(), 'ssg-test-'));
}

function writeFixture(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, content, 'utf8');
  }
}

describe('toSlug', () => {
  it('strips the extension and cleans the name', () => {
    expect(toSlug('hello-world.md')).toBe('hello-world');
  });

  it('handles markdown extension and nested paths', () => {
    expect(toSlug('blog/my first post.markdown')).toBe('blog/my-first-post');
  });
});

describe('loadPages', () => {
  it('loads all markdown files with parsed metadata', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'first.md': '---\ntitle: First Post\ndate: 2024-01-01\ntags: [a, b]\n---\nHello **world**',
      'second.md': '---\ntitle: Second Post\ndate: 2024-01-02\n---\nSecond',
    });

    const pages = await loadPages(dir);
    expect(pages).toHaveLength(2);
    expect(pages.map((p) => p.title)).toEqual(['Second Post', 'First Post']);
    expect(pages[1].tags).toEqual(['a', 'b']);
    expect(pages[1].html).toContain('<strong>world</strong>');
  });

  it('recurses into nested directories', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'blog/deep.md': '---\ntitle: Deep\n---\nBody',
    });

    const pages = await loadPages(dir);
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('blog/deep');
  });

  it('falls back to a derived title when frontmatter lacks one', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'untitled-page.md': '# Heading only' });

    const pages = await loadPages(dir);
    expect(pages[0].title).toBe('Untitled Page');
  });
});

describe('renderPage', () => {
  it('produces a full html document', () => {
    const page = {
      title: 'Test',
      date: '2024-01-01',
      tags: ['ts', 'cli'],
      slug: 'test',
      source: 'test.md',
      html: '<p>Content</p>',
    };
    const html = renderPage(page);
    expect(html).toContain('<title>Test</title>');
    expect(html).toContain('<h1>Test</h1>');
    expect(html).toContain('2024-01-01');
    expect(html).toContain('Content');
    expect(html).toMatch(/<a[^>]*href="index.html"/);
  });
});

describe('renderIndex', () => {
  it('lists all pages with links', () => {
    const pages = [
      { title: 'A', date: '2024-01-01', tags: [], slug: 'a', source: 'a.md', html: '' },
      { title: 'B', date: '', tags: [], slug: 'b', source: 'b.md', html: '' },
    ];
    const html = renderIndex(pages);
    expect(html).toContain('href="a.html"');
    expect(html).toContain('href="b.html"');
    expect(html).toContain('>A</a>');
    expect(html).toContain('>B</a>');
  });
});

describe('buildSite', () => {
  it('writes index.html and a page file per markdown file', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n# One\n',
      'content/two.md': '---\ntitle: Two\ndate: 2024-01-02\n---\n# Two\n',
    });

    const result = await buildSite(path.join(dir, 'content'), path.join(dir, 'dist'));

    expect(result.pages).toHaveLength(2);
    expect(result.files).toHaveLength(3);

    expect(existsSync(path.join(dir, 'dist', 'index.html'))).toBe(true);
    expect(existsSync(path.join(dir, 'dist', 'one.html'))).toBe(true);
    expect(existsSync(path.join(dir, 'dist', 'two.html'))).toBe(true);

    const index = readFileSync(path.join(dir, 'dist', 'index.html'), 'utf8');
    expect(index).toContain('href="one.html"');
    expect(index).toContain('href="two.html"');

    const one = readFileSync(path.join(dir, 'dist', 'one.html'), 'utf8');
    expect(one).toContain('<h1>One</h1>');
  });

  it('preserves nested directory structure in output', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/blog/entry.md': '---\ntitle: Entry\n---\nBody',
    });

    await buildSite(path.join(dir, 'content'), path.join(dir, 'dist'));
    expect(existsSync(path.join(dir, 'dist', 'blog', 'entry.html'))).toBe(true);
    expect(existsSync(path.join(dir, 'dist', 'blog'))).toBe(true);
  });

  it('throws a helpful error when the content directory does not exist', async () => {
    const dir = makeTempDir();
    await expect(buildSite(path.join(dir, 'missing'), path.join(dir, 'dist'))).rejects.toThrow();
  });
});
