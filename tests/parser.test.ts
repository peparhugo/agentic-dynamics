import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  findMarkdownFiles,
  normalizeTags,
  parseMarkdownFile,
  slugify,
  titleFromSlug,
} from '../src/parser';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-parser-'));
}

describe('slugify', () => {
  it('lowercases and hyphenates', () => {
    expect(slugify('Hello World.md')).toBe('hello-world');
  });

  it('strips non-alphanumeric characters', () => {
    expect(slugify('My Post! #1.md')).toBe('my-post-1');
  });

  it('handles nested paths', () => {
    expect(slugify('blog/My Post.md')).toBe('blog-my-post');
  });
});

describe('titleFromSlug', () => {
  it('capitalizes each word', () => {
    expect(titleFromSlug('hello-world')).toBe('Hello World');
  });
});

describe('normalizeTags', () => {
  it('returns array input as trimmed strings', () => {
    expect(normalizeTags(['a', ' b ', 'c'])).toEqual(['a', 'b', 'c']);
  });

  it('splits comma separated strings', () => {
    expect(normalizeTags('a, b,c')).toEqual(['a', 'b', 'c']);
  });

  it('returns empty array for undefined', () => {
    expect(normalizeTags(undefined)).toEqual([]);
  });

  it('filters out empty entries', () => {
    expect(normalizeTags(['a', '', '  '])).toEqual(['a']);
  });
});

describe('parseMarkdownFile', () => {
  let dir: string;

  beforeEach(() => {
    dir = makeTempDir();
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('parses frontmatter and converts markdown to html', () => {
    const filePath = path.join(dir, 'my-post.md');
    fs.writeFileSync(
      filePath,
      `---\ntitle: My Post\ndate: 2026-01-01\ntags: [a, b]\n---\n\n# Heading\n\nSome **bold** text.\n`
    );

    const page = parseMarkdownFile(filePath, dir);

    expect(page.title).toBe('My Post');
    expect(page.date).toBe('2026-01-01');
    expect(page.tags).toEqual(['a', 'b']);
    expect(page.slug).toBe('my-post');
    expect(page.outputPath).toBe('my-post.html');
    expect(page.html).toContain('<h1>Heading</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
  });

  it('falls back to a title derived from the filename when missing', () => {
    const filePath = path.join(dir, 'no-frontmatter-title.md');
    fs.writeFileSync(filePath, `---\ndate: 2026-01-01\n---\n\nBody text.\n`);

    const page = parseMarkdownFile(filePath, dir);

    expect(page.title).toBe('No Frontmatter Title');
    expect(page.tags).toEqual([]);
  });

  it('defaults date and tags when entirely absent', () => {
    const filePath = path.join(dir, 'bare.md');
    fs.writeFileSync(filePath, 'Just content, no frontmatter.\n');

    const page = parseMarkdownFile(filePath, dir);

    expect(page.date).toBe('');
    expect(page.tags).toEqual([]);
    expect(page.title).toBe('Bare');
  });
});

describe('findMarkdownFiles', () => {
  let dir: string;

  beforeEach(() => {
    dir = makeTempDir();
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('returns an empty array when the directory does not exist', () => {
    expect(findMarkdownFiles(path.join(dir, 'missing'))).toEqual([]);
  });

  it('finds markdown files recursively and ignores other extensions', () => {
    fs.writeFileSync(path.join(dir, 'a.md'), '# A');
    fs.writeFileSync(path.join(dir, 'notes.txt'), 'ignore me');
    fs.mkdirSync(path.join(dir, 'sub'));
    fs.writeFileSync(path.join(dir, 'sub', 'b.md'), '# B');

    const files = findMarkdownFiles(dir).map((f) => path.relative(dir, f));

    expect(files.sort()).toEqual(['a.md', path.join('sub', 'b.md')].sort());
  });
});
