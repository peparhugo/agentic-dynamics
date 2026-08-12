import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, collectPages } from './build';

describe('buildSite', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-build-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  function writeContent(name: string, content: string): void {
    fs.writeFileSync(path.join(contentDir, name), content, 'utf-8');
  }

  it('generates an index.html and a page per markdown file', () => {
    writeContent('first.md', '---\ntitle: First\ndate: 2024-01-01\n---\n\nHello *world*.');
    writeContent('second.md', '---\ntitle: Second\n---\n\nSecond body.');

    const pages = buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'README.txt'))).toBe(false);

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('<a href="first.html">First</a>');
    expect(index).toContain('<a href="second.html">Second</a>');

    const page = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf-8');
    expect(page).toContain('<em>world</em>');
    expect(page).toContain('<time datetime="2024-01-01">2024-01-01</time>');
  });

  it('ignores non-markdown files', () => {
    writeContent('keep.md', '---\ntitle: Keep\n---\n\nx');
    fs.writeFileSync(path.join(contentDir, 'notes.txt'), 'not markdown', 'utf-8');
    fs.writeFileSync(path.join(contentDir, 'image.png'), 'fake', 'utf-8');

    const pages = buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'keep.html'))).toBe(true);
  });

  it('cleans the output directory before writing', () => {
    writeContent('a.md', '---\ntitle: A\n---\n\nx');
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(path.join(outputDir, 'stale.html'), 'stale', 'utf-8');

    buildSite({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'stale.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => buildSite({ contentDir: path.join(root, 'nope'), outputDir })).toThrow(
      'does not exist'
    );
  });
});

describe('collectPages', () => {
  it('returns no pages for an empty directory', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-empty-'));
    try {
      const pages = collectPages(dir);
      expect(pages).toEqual([]);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});
