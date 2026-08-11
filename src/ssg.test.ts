import fs from 'fs';
import path from 'path';
import { parseFiles } from './parser';
import { generateSite } from './generator';
import { PageData } from './types';

const tmpDir = path.join(__dirname, '..', '.test-tmp');

function setupContentDir(files: Record<string, string>): string {
  const contentDir = path.join(tmpDir, 'content');
  if (fs.existsSync(contentDir)) {
    fs.rmSync(contentDir, { recursive: true });
  }
  fs.mkdirSync(contentDir, { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    fs.writeFileSync(path.join(contentDir, name), body);
  }
  return contentDir;
}

function outputDir(): string {
  const dir = path.join(tmpDir, 'dist');
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true });
  }
  return dir;
}

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true });
  }
});

describe('parseFiles', () => {
  it('parses a single markdown file with frontmatter', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - cli
---
# Hello

This is a test post.`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages).toHaveLength(1);
    expect(result.pages[0].slug).toBe('hello');
    expect(result.pages[0].frontmatter.title).toBe('Hello World');
    expect(result.pages[0].frontmatter.date).toBe('2024-01-15');
    expect(result.pages[0].frontmatter.tags).toEqual(['typescript', 'cli']);
    expect(result.pages[0].html).toContain('<h1>Hello</h1>');
    expect(result.pages[0].html).toContain('<p>This is a test post.</p>');
  });

  it('uses filename as title when no title in frontmatter', () => {
    const contentDir = setupContentDir({
      'no-title.md': `---
date: 2024-02-01
---
# Content`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages[0].frontmatter.title).toBe('no-title');
  });

  it('handles missing date and tags gracefully', () => {
    const contentDir = setupContentDir({
      'minimal.md': `---
title: Minimal
---
Just content.`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages[0].frontmatter.date).toBe('');
    expect(result.pages[0].frontmatter.tags).toEqual([]);
  });

  it('parses multiple files', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages).toHaveLength(2);
  });

  it('ignores non-markdown files', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: Post
date: 2024-01-01
---
# Post`,
      'readme.txt': 'not markdown',
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages).toHaveLength(1);
    expect(result.pages[0].slug).toBe('post');
  });

  it('throws when content directory does not exist', () => {
    expect(() =>
      parseFiles({ contentDir: '/nonexistent/dir', outputDir: outputDir() })
    ).toThrow('Content directory not found');
  });
});

describe('generateSite', () => {
  it('generates index.html and individual pages', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: My Post
date: 2024-03-10
tags:
  - blog
---
# My Post

Content here.`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist);

    const indexHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<!DOCTYPE html>');
    expect(indexHtml).toContain('My Post');
    expect(indexHtml).toContain('post.html');
    expect(indexHtml).toContain('2024-03-10');
    expect(indexHtml).toContain('blog');

    const postHtml = fs.readFileSync(path.join(dist, 'post.html'), 'utf-8');
    expect(postHtml).toContain('<!DOCTYPE html>');
    expect(postHtml).toContain('<h1>My Post</h1>');
    expect(postHtml).toContain('<h1>My Post</h1>');
  });

  it('sorts index by date descending', () => {
    const contentDir = setupContentDir({
      'old.md': `---
title: Old Post
date: 2024-01-01
---
# Old`,
      'new.md': `---
title: New Post
date: 2024-06-01
---
# New`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist);

    const indexHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf-8');
    const newIdx = indexHtml.indexOf('New Post');
    const oldIdx = indexHtml.indexOf('Old Post');
    expect(newIdx).toBeLessThan(oldIdx);
  });

  it('creates output directory if it does not exist', () => {
    const contentDir = setupContentDir({
      'p.md': `---
title: P
date: 2024-01-01
---
# P`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist);
    expect(fs.existsSync(dist)).toBe(true);
    expect(fs.existsSync(path.join(dist, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(dist, 'p.html'))).toBe(true);
  });
});
