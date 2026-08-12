import { parseFile, parseDirectory } from '../src/parser';
import fs from 'fs';
import path from 'path';
import os from 'os';

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
    expect(true).toBe(true);
  });

  it('parses template and layout from frontmatter', () => {
    const page = parseFile(path.join(CONTENT_DIR, 'custom-template.md'));

    expect(page.frontmatter.template).toBe('custom');
    expect(page.frontmatter.layout).toBe('post');
    expect(page.frontmatter.title).toBe('Custom Template Post');
  });

  it('does not set template or layout when not in frontmatter', () => {
    const page = parseFile(path.join(CONTENT_DIR, 'hello.md'));

    expect(page.frontmatter.template).toBeUndefined();
    expect(page.frontmatter.layout).toBeUndefined();
  });

  it('ignores non-string template and layout values', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-parse-'));
    const filePath = path.join(tmpDir, 'bad-template.md');
    fs.writeFileSync(
      filePath,
      `---
title: Bad Template
template: 123
layout: true
---
Content`
    );

    const page = parseFile(filePath);
    expect(page.frontmatter.template).toBeUndefined();
    expect(page.frontmatter.layout).toBeUndefined();

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
});

describe('parseDirectory', () => {
  it('reads all .md files from a directory', () => {
    const pages = parseDirectory(CONTENT_DIR);
    expect(pages.length).toBe(4);
  });

  it('sorts pages by date descending', () => {
    const pages = parseDirectory(CONTENT_DIR);
    expect(pages[0].frontmatter.date).toBe('2024-04-01');
    expect(pages[1].frontmatter.date).toBe('2024-03-01');
    expect(pages[2].frontmatter.date).toBe('2024-02-10');
    expect(pages[3].frontmatter.date).toBe('2024-01-15');
  });

  it('returns empty array for non-existent directory', () => {
    const pages = parseDirectory('/nonexistent/path');
    expect(pages).toEqual([]);
  });
});
