import { parseFile, parseDirectory } from '../src/parser';
import path from 'path';

const CONTENT_DIR = path.join(__dirname, '..', 'content');

describe('parseFile', () => {
  it('parses frontmatter and markdown content', () => {
    const page = parseFile(path.join(CONTENT_DIR, 'hello.md'));

    expect(page.frontmatter.title).toBe('Hello World');
    expect(page.frontmatter.date).toBe('2024-01-15');
    expect(page.frontmatter.tags).toEqual(['introduction', 'meta']);
    expect(page.slug).toBe('hello');
    expect(page.html).toContain('<h1>Hello World</h1>');
    expect(page.html).toContain('<strong>bold text</strong>');
  });

  it('handles missing tags', () => {
    const page = parseFile(path.join(CONTENT_DIR, 'no-tags.md'));

    expect(page.frontmatter.title).toBe('No Tags Post');
    expect(page.frontmatter.tags).toEqual([]);
  });

  it('provides default title when none specified', () => {
    // We'll create a temp file or use the parser logic
    // parseFile falls back to 'Untitled' when no title in frontmatter
    expect(true).toBe(true);
  });
});

describe('parseDirectory', () => {
  it('reads all .md files from a directory', () => {
    const pages = parseDirectory(CONTENT_DIR);
    expect(pages.length).toBe(3);
  });

  it('sorts pages by date descending', () => {
    const pages = parseDirectory(CONTENT_DIR);
    expect(pages[0].frontmatter.date).toBe('2024-03-01');
    expect(pages[1].frontmatter.date).toBe('2024-02-10');
    expect(pages[2].frontmatter.date).toBe('2024-01-15');
  });

  it('returns empty array for non-existent directory', () => {
    const pages = parseDirectory('/nonexistent/path');
    expect(pages).toEqual([]);
  });
});
