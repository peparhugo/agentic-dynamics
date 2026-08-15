import fs from 'fs';
import os from 'os';
import path from 'path';

import { buildSite } from '../src/site';

function makeTempContentDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-content-'));
  return dir;
}

function writeFixture(contentDir: string): void {
  fs.writeFileSync(
    path.join(contentDir, 'hello.md'),
    `---
title: Hello World
date: 2024-01-15
tags:
  - intro
---
# Welcome

This is the **first** post.
`
  );
  fs.writeFileSync(
    path.join(contentDir, 'about.md'),
    `---
title: About
date: 2024-03-02
tags: [meta]
---
# About Us

We build things.
`
  );
  fs.mkdirSync(path.join(contentDir, 'nested'), { recursive: true });
  fs.writeFileSync(
    path.join(contentDir, 'nested', 'deep.md'),
    `---
title: Deep Page
---
Nested content.
`
  );
}

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTempContentDir();
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-dist-'));
    writeFixture(contentDir);
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('generates an index.html and one HTML file per page', () => {
    const result = buildSite({ contentDir, outputDir });

    expect(result.posts).toHaveLength(3);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'nested', 'deep.html'))).toBe(true);
    expect(result.filesWritten).toHaveLength(4);
  });

  it('lists every page in the index with a title and link', () => {
    buildSite({ contentDir, outputDir });

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('Hello World');
    expect(index).toContain('About');
    expect(index).toContain('Deep Page');
    expect(index).toContain('href="hello.html"');
    expect(index).toContain('href="about.html"');
    expect(index).toContain('href="nested/deep.html"');
  });

  it('orders pages by date, newest first', () => {
    const result = buildSite({ contentDir, outputDir });

    const slugs = result.posts.map((post) => post.slug);
    expect(slugs.indexOf('about')).toBeLessThan(slugs.indexOf('hello'));
  });

  it('renders markdown content into each page without frontmatter delimiters', () => {
    buildSite({ contentDir, outputDir });

    const page = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>first</strong>');
    expect(page).not.toContain('---');
  });

  it('honours a custom output directory', () => {
    const custom = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-custom-'));
    try {
      buildSite({ contentDir, outputDir: custom });
      expect(fs.existsSync(path.join(custom, 'index.html'))).toBe(true);
      expect(fs.existsSync(path.join(custom, 'hello.html'))).toBe(true);
    } finally {
      fs.rmSync(custom, { recursive: true, force: true });
    }
  });

  it('produces an empty index for a missing content directory', () => {
    const result = buildSite({
      contentDir: path.join(contentDir, 'does-not-exist'),
      outputDir,
    });

    expect(result.posts).toHaveLength(0);
    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('(no pages)');
  });
});
