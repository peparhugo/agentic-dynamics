import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  buildSite,
  findMarkdownFiles,
  readPages,
  sortPages,
  renderPage,
  renderIndex,
} from '../src/site';
import { Page } from '../src/types';

interface TempDir {
  dir: string;
  cleanup: () => void;
}

function makeTempDir(): TempDir {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  return { dir, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

function writeContentFiles(contentDir: string): void {
  fs.mkdirSync(contentDir, { recursive: true });
  fs.writeFileSync(
    path.join(contentDir, 'one.md'),
    '---\ntitle: First Page\ndate: 2024-01-01\ntags: [a, b]\n---\n# First\nBody **here**.'
  );
  fs.writeFileSync(
    path.join(contentDir, 'two.md'),
    '---\ntitle: Second Page\ndate: 2024-02-01\ntags: [b]\n---\n# Second\nBody two.'
  );
}

describe('findMarkdownFiles', () => {
  it('finds markdown files recursively', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    fs.mkdirSync(path.join(contentDir, 'sub'), { recursive: true });
    fs.writeFileSync(path.join(contentDir, 'a.md'), 'a');
    fs.writeFileSync(path.join(contentDir, 'sub', 'b.mdx'), 'b');
    fs.writeFileSync(path.join(contentDir, 'sub', 'c.txt'), 'c');

    const files = findMarkdownFiles(contentDir);
    expect(files.map((f) => path.basename(f)).sort()).toEqual(['a.md', 'b.mdx']);
    cleanup();
  });
});

describe('readPages', () => {
  it('reads and parses all markdown files in a directory', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    writeContentFiles(contentDir);

    const pages = readPages(contentDir);
    expect(pages).toHaveLength(2);
    const titles = pages.map((p) => p.title).sort();
    expect(titles).toEqual(['First Page', 'Second Page']);
    cleanup();
  });
});

describe('sortPages', () => {
  it('sorts newest first by date', () => {
    const pages: Page[] = [
      { title: 'Old', slug: 'old', date: '2020-01-01', tags: [], body: '', html: '', excerpt: '', filePath: 'old.md' },
      { title: 'New', slug: 'new', date: '2024-01-01', tags: [], body: '', html: '', excerpt: '', filePath: 'new.md' },
    ];
    const sorted = sortPages(pages);
    expect(sorted[0].title).toBe('New');
    expect(sorted[1].title).toBe('Old');
  });

  it('sorts pages without dates last', () => {
    const pages: Page[] = [
      { title: 'Dated', slug: 'd', date: '2024-01-01', tags: [], body: '', html: '', excerpt: '', filePath: 'd.md' },
      { title: 'Undated', slug: 'u', tags: [], body: '', html: '', excerpt: '', filePath: 'u.md' },
    ];
    const sorted = sortPages(pages);
    expect(sorted[0].title).toBe('Dated');
    expect(sorted[1].title).toBe('Undated');
  });
});

describe('buildSite', () => {
  it('generates index.html and a page per markdown file', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContentFiles(contentDir);

    const result = buildSite(contentDir, outDir);
    expect(result.pages).toBe(2);
    expect(result.files).toContain('index.html');
    expect(result.files).toContain('first-page.html');
    expect(result.files).toContain('second-page.html');

    const index = fs.readFileSync(path.join(outDir, 'index.html'), 'utf8');
    expect(index).toContain('First Page');
    expect(index).toContain('first-page.html');
    expect(index).toContain('Second Page');

    const page = fs.readFileSync(path.join(outDir, 'first-page.html'), 'utf8');
    expect(page).toContain('<h1>First Page</h1>');
    expect(page).toContain('<strong>here</strong>');
    cleanup();
  });

  it('creates the output directory when it does not exist', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'nested', 'dist');
    writeContentFiles(contentDir);

    buildSite(contentDir, outDir);
    expect(fs.existsSync(path.join(outDir, 'index.html'))).toBe(true);
    cleanup();
  });

  it('builds an empty index when there are no pages', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    fs.mkdirSync(contentDir, { recursive: true });

    const result = buildSite(contentDir, outDir);
    expect(result.pages).toBe(0);
    expect(fs.existsSync(path.join(outDir, 'index.html'))).toBe(true);
    cleanup();
  });

  it('throws when the content directory is missing', () => {
    const { dir, cleanup } = makeTempDir();
    expect(() => buildSite(path.join(dir, 'nope'), path.join(dir, 'dist'))).toThrow(
      /content directory not found/
    );
    cleanup();
  });
});

describe('renderPage / renderIndex', () => {
  const page: Page = {
    title: 'My <Post>',
    slug: 'my-post',
    date: '2024-01-01',
    tags: ['typescript'],
    body: '',
    html: '<p>Hello</p>',
    excerpt: 'Hello',
    filePath: 'my-post.md',
  };

  it('escapes the title in rendered pages', () => {
    const html = renderPage(page);
    expect(html).toContain('&lt;Post&gt;');
    expect(html).toContain('<p>Hello</p>');
    expect(html).toContain('href="./index.html"');
  });

  it('renders a link to each page in the index', () => {
    const html = renderIndex([page]);
    expect(html).toContain('my-post.html');
    expect(html).toContain('My &lt;Post&gt;');
    expect(html).toContain('Hello');
  });
});
