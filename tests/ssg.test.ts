import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('build', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTempDir();
    outputDir = path.join(makeTempDir(), 'dist');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(path.dirname(outputDir), { recursive: true, force: true });
  });

  it('generates an index.html and one HTML file per Markdown page', () => {
    writeFile(
      contentDir,
      'hello.md',
      '---\ntitle: Hello\n---\n\n# Hello\n\nThis is **bold**.\n'
    );
    writeFile(contentDir, 'world.md', '# World\n\nSecond page.\n');

    const result = build({ contentDir, outputDir });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'world.html'))).toBe(true);
  });

  it('converts Markdown to HTML without leaking frontmatter delimiters', () => {
    writeFile(
      contentDir,
      'post.md',
      '---\ntitle: Post\n---\n\n# Heading\n\nSome paragraph.\n'
    );

    build({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(html).toContain('<h1>Heading</h1>');
    expect(html).toContain('<p>Some paragraph.</p>');
    expect(html).not.toContain('---');
    expect(html).not.toContain('<hr');
  });

  it('renders the title, date, and tags from frontmatter', () => {
    writeFile(
      contentDir,
      'post.md',
      [
        '---',
        'title: My Post',
        'date: 2024-05-01',
        'tags:',
        '  - a',
        '  - b',
        '---',
        'Body text.',
      ].join('\n')
    );

    build({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(html).toContain('<title>My Post</title>');
    expect(html).toContain('<h1>My Post</h1>');
    expect(html).toContain('2024-05-01');
    expect(html).toContain('<li>a</li>');
    expect(html).toContain('<li>b</li>');
  });

  it('lists every page in index.html with a link', () => {
    writeFile(contentDir, 'one.md', '---\ntitle: One\n---\nBody');
    writeFile(contentDir, 'two.md', '---\ntitle: Two\n---\nBody');

    build({ contentDir, outputDir });

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('href="one.html"');
    expect(index).toContain('href="two.html"');
    expect(index).toContain('One');
    expect(index).toContain('Two');
  });

  it('sorts index entries by date in descending order', () => {
    writeFile(contentDir, 'old.md', '---\ntitle: Old\ndate: 2023-01-01\n---\nBody');
    writeFile(contentDir, 'new.md', '---\ntitle: New\ndate: 2024-01-01\n---\nBody');

    build({ contentDir, outputDir });

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index.indexOf('new.html')).toBeLessThan(index.indexOf('old.html'));
  });

  it('uses the filename as the title when no title is provided', () => {
    writeFile(contentDir, 'untitled.md', '# Body');
    build({ contentDir, outputDir });
    const html = fs.readFileSync(path.join(outputDir, 'untitled.html'), 'utf-8');
    expect(html).toContain('<h1>untitled</h1>');
  });

  it('ignores non-Markdown files in the content directory', () => {
    writeFile(contentDir, 'note.txt', 'ignore me');
    writeFile(contentDir, 'real.md', '---\ntitle: Real\n---\nBody');

    const result = build({ contentDir, outputDir });

    expect(result.pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'real.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'note.txt.html'))).toBe(false);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => build({ contentDir: path.join(contentDir, 'missing'), outputDir })).toThrow(
      /Content directory not found/
    );
  });

  it('escapes HTML in page titles', () => {
    writeFile(contentDir, 'x.md', '---\ntitle: <script>alert(1)</script>\n---\nBody');
    build({ contentDir, outputDir });
    const html = fs.readFileSync(path.join(outputDir, 'x.html'), 'utf-8');
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
  });
});
