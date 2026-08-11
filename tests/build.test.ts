import fs from 'fs';
import path from 'path';
import { build } from '../src/build';

const FIXTURES = path.resolve(__dirname, '..', 'content');
const OUT = path.resolve(__dirname, '..', 'test-dist');

beforeEach(() => {
  if (fs.existsSync(OUT)) {
    fs.rmSync(OUT, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(OUT)) {
    fs.rmSync(OUT, { recursive: true, force: true });
  }
});

describe('build', () => {
  test('generates index.html and page html files', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    expect(fs.existsSync(path.join(OUT, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'first-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'another-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'no-date.html'))).toBe(true);
  });

  test('index.html lists all pages', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const indexHtml = fs.readFileSync(path.join(OUT, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('My First Post');
    expect(indexHtml).toContain('Another Post');
    expect(indexHtml).toContain('No Date Post');
    expect(indexHtml).toContain('<li><a href="first-post.html">My First Post</a>');
    expect(indexHtml).toContain('<li><a href="another-post.html">Another Post</a>');
    expect(indexHtml).toContain('<li><a href="no-date.html">No Date Post</a>');
  });

  test('page html contains frontmatter data', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const firstPost = fs.readFileSync(path.join(OUT, 'first-post.html'), 'utf-8');
    expect(firstPost).toContain('<title>My First Post</title>');
    expect(firstPost).toContain('<h1>My First Post</h1>');
    expect(firstPost).toContain('2025-06-01');
    expect(firstPost).toContain('hello, world');

    const anotherPost = fs.readFileSync(path.join(OUT, 'another-post.html'), 'utf-8');
    expect(anotherPost).toContain('<title>Another Post</title>');
  });

  test('markdown content is converted to HTML', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const firstPost = fs.readFileSync(path.join(OUT, 'first-post.html'), 'utf-8');
    expect(firstPost).toContain('<h1>Hello World</h1>');
    expect(firstPost).toContain('<p>This is the first post.</p>');

    const anotherPost = fs.readFileSync(path.join(OUT, 'another-post.html'), 'utf-8');
    expect(anotherPost).toContain('<h2>Getting Started</h2>');
    expect(anotherPost).toContain('<p>Some content here.</p>');
  });

  test('page with no date or tags does not crash', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const noDate = fs.readFileSync(path.join(OUT, 'no-date.html'), 'utf-8');
    expect(noDate).toContain('<title>No Date Post</title>');
    expect(noDate).not.toContain('class="date"');
    expect(noDate).not.toContain('class="tags"');
  });

  test('pages are ordered correctly (with dates first, then title)', () => {
    // Create temp fixtures with known dates for ordering test
    const tempContent = path.resolve(__dirname, '..', 'temp-content');
    const tempOut = path.resolve(__dirname, '..', 'temp-dist');

    try {
      fs.mkdirSync(tempContent, { recursive: true });
      fs.writeFileSync(
        path.join(tempContent, 'a.md'),
        `---\ntitle: Alpha\ndate: 2025-01-01\n---\nContent`
      );
      fs.writeFileSync(
        path.join(tempContent, 'b.md'),
        `---\ntitle: Beta\ndate: 2025-06-01\n---\nContent`
      );
      fs.writeFileSync(
        path.join(tempContent, 'c.md'),
        `---\ntitle: Gamma\n---\nContent`
      );

      build({ contentDir: tempContent, outputDir: tempOut });

      const indexHtml = fs.readFileSync(path.join(tempOut, 'index.html'), 'utf-8');
      const betaIdx = indexHtml.indexOf('Beta');
      const alphaIdx = indexHtml.indexOf('Alpha');
      const gammaIdx = indexHtml.indexOf('Gamma');

      expect(betaIdx).toBeLessThan(alphaIdx);
      expect(alphaIdx).toBeLessThan(gammaIdx);
    } finally {
      if (fs.existsSync(tempContent)) fs.rmSync(tempContent, { recursive: true, force: true });
      if (fs.existsSync(tempOut)) fs.rmSync(tempOut, { recursive: true, force: true });
    }
  });

  test('throws on missing content directory', () => {
    expect(() => {
      build({ contentDir: '/nonexistent/path', outputDir: OUT });
    }).toThrow('Content directory not found');
  });

  test('throws on missing title in frontmatter', () => {
    const tempContent = path.resolve(__dirname, '..', 'bad-content');
    const tempOut = path.resolve(__dirname, '..', 'bad-dist');
    try {
      fs.mkdirSync(tempContent, { recursive: true });
      fs.writeFileSync(path.join(tempContent, 'bad.md'), 'No frontmatter here');

      expect(() => {
        build({ contentDir: tempContent, outputDir: tempOut });
      }).toThrow('Missing title in frontmatter');
    } finally {
      if (fs.existsSync(tempContent)) fs.rmSync(tempContent, { recursive: true, force: true });
      if (fs.existsSync(tempOut)) fs.rmSync(tempOut, { recursive: true, force: true });
    }
  });
});
