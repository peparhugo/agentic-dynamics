import { describe, it, expect } from 'vitest';
import { parseFrontmatter, slugify, readPost } from '../src/frontmatter.js';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(__dirname, 'fixtures', 'content');

describe('parseFrontmatter', () => {
  it('parses title from frontmatter', () => {
    const input = `---
title: "My Post"
date: "2024-01-01"
---
Content here.`;

    const result = parseFrontmatter(input, '/path/to/my-post.md');
    expect(result.frontmatter.title).toBe('My Post');
    expect(result.content.trim()).toBe('Content here.');
  });

  it('parses date field', () => {
    const input = `---
title: Test
date: "2024-06-15"
---
Body`;

    const result = parseFrontmatter(input, '/path/to/test.md');
    expect(result.frontmatter.date).toBe('2024-06-15');
  });

  it('parses tags as an array', () => {
    const input = `---
title: Tagged
tags: ["javascript", "typescript", "testing"]
---
Body`;

    const result = parseFrontmatter(input, '/path/to/tagged.md');
    expect(result.frontmatter.tags).toEqual(['javascript', 'typescript', 'testing']);
  });

  it('parses draft flag', () => {
    const input = `---
title: Draft
draft: true
---
Hidden content`;

    const result = parseFrontmatter(input, '/path/to/draft.md');
    expect(result.frontmatter.draft).toBe(true);
  });

  it('defaults draft to false when not set', () => {
    const input = `---
title: Published
---
Content`;

    const result = parseFrontmatter(input, '/path/to/published.md');
    expect(result.frontmatter.draft).toBe(false);
  });

  it('handles missing frontmatter gracefully', () => {
    const input = `Just raw markdown with no frontmatter.`;
    const result = parseFrontmatter(input, '/path/to/raw.md');

    expect(result.frontmatter.title).toBe('raw');
    expect(result.frontmatter.draft).toBe(false);
    expect(result.content.trim()).toBe('Just raw markdown with no frontmatter.');
  });

  it('handles empty frontmatter', () => {
    const input = `---
---
Body text`;

    const result = parseFrontmatter(input, '/path/to/empty.md');
    expect(result.frontmatter.title).toBe('empty');
    expect(result.content.trim()).toBe('Body text');
  });

  it('handles tags as YAML list', () => {
    const input = `---
title: List
tags:
  - python
  - go
  - rust
---
Body`;

    const result = parseFrontmatter(input, '/path/to/list.md');
    expect(result.frontmatter.tags).toEqual(['python', 'go', 'rust']);
  });
});

describe('slugify', () => {
  it('generates slug from filename', () => {
    expect(slugify('my-great-post.md')).toBe('my-great-post');
  });

  it('lowercases the filename', () => {
    expect(slugify('UPPERCASE-POST.md')).toBe('uppercase-post');
  });

  it('handles full paths', () => {
    expect(slugify('/some/deep/path/blog-post.md')).toBe('blog-post');
  });

  it('replaces spaces', () => {
    expect(slugify('hello world.md')).toBe('hello-world');
  });
});

describe('readPost', () => {
  it('reads and parses a markdown file', async () => {
    const post = await readPost(join(FIXTURES, 'post-with-tags.md'));

    expect(post.frontmatter.title).toBe('Hello World');
    expect(post.frontmatter.date).toBe('2024-01-15');
    expect(post.frontmatter.tags).toEqual(['javascript', 'tutorial']);
    expect(post.frontmatter.draft).toBeFalsy();
    expect(post.slug).toBe('post-with-tags');
    expect(post.url).toBe('/post-with-tags/');
    expect(post.content).toContain('This is my first post');
  });

  it('detects draft posts', async () => {
    const post = await readPost(join(FIXTURES, 'draft-post.md'));

    expect(post.frontmatter.title).toBe('Draft Post');
    expect(post.frontmatter.draft).toBe(true);
  });

  it('handles posts with no frontmatter', async () => {
    const post = await readPost(join(FIXTURES, 'no-frontmatter.md'));

    expect(post.frontmatter.title).toBe('no-frontmatter');
    expect(post.frontmatter.draft).toBe(false);
    expect(post.content).toContain('def hello()');
  });

  it('generates a description from content', async () => {
    const post = await readPost(join(FIXTURES, 'post-with-tags.md'));

    expect(post.description.length).toBeGreaterThan(0);
    expect(post.description).not.toContain('\n');
  });
});
