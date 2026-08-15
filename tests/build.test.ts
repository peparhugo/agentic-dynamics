import fs from 'fs';
import os from 'os';
import path from 'path';
import { build, buildPage, findMarkdownFiles } from '../src/build';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('static site build', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-content-');
    outputDir = makeTmpDir('ssg-dist-');
    fs.writeFileSync(
      path.join(contentDir, 'first-post.md'),
      `---
title: First Post
date: 2024-01-01
tags: [intro, news]
---
# Hello

This is the **first** post.`
    );
    fs.writeFileSync(
      path.join(contentDir, 'second-post.md'),
      `---
title: Second Post
date: 2024-02-01
tags: update
---
Some more content here.`
    );
    fs.writeFileSync(path.join(contentDir, 'no-frontmatter.md'), '# No Frontmatter\n\nJust text.');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('finds all markdown files in the content directory, sorted', () => {
    const files = findMarkdownFiles(contentDir);
    expect(files).toEqual(['first-post.md', 'no-frontmatter.md', 'second-post.md']);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => findMarkdownFiles(path.join(contentDir, 'missing'))).toThrow(/Content directory not found/);
  });

  it('builds a single page with frontmatter applied', () => {
    const page = buildPage(contentDir, 'first-post.md');
    expect(page.title).toBe('First Post');
    expect(page.date).toBe('2024-01-01');
    expect(page.tags).toEqual(['intro', 'news']);
    expect(page.outputPath).toBe('first-post.html');
    expect(page.html).toContain('<h1>First Post</h1>');
    expect(page.html).toContain('<strong>first</strong>');
  });

  it('falls back to the filename slug as title when frontmatter has none', () => {
    const page = buildPage(contentDir, 'no-frontmatter.md');
    expect(page.title).toBe('no-frontmatter');
    expect(page.html).toContain('<h1>No Frontmatter</h1>');
  });

  it('normalizes a single string tag into an array', () => {
    const page = buildPage(contentDir, 'second-post.md');
    expect(page.tags).toEqual(['update']);
  });

  it('writes an HTML file per page plus an index.html to the output directory', () => {
    const result = build({ contentDir, outputDir });
    expect(result.pages).toHaveLength(3);

    const distFiles = fs.readdirSync(outputDir).sort();
    expect(distFiles).toEqual(
      ['first-post.html', 'index.html', 'no-frontmatter.html', 'second-post.html'].sort()
    );

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('href="first-post.html"');
  });

  it('creates the output directory if it does not exist', () => {
    const nestedOutput = path.join(outputDir, 'nested', 'dist');
    build({ contentDir, outputDir: nestedOutput });
    expect(fs.existsSync(path.join(nestedOutput, 'index.html'))).toBe(true);
  });
});
