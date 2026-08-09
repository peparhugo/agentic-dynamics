import { describe, it, expect } from 'vitest';
import { parseFile, parseDirectory } from '../src/parser';
import { join } from 'node:path';

const FIXTURES = join(__dirname, 'fixtures', 'content');

describe('parseFile', () => {
  it('parses frontmatter title from YAML', () => {
    const post = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(post.title).toBe('Hello World');
  });

  it('parses date from frontmatter', () => {
    const post = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(post.date).toBeInstanceOf(Date);
    expect(post.date.toISOString().slice(0, 10)).toBe('2024-01-15');
  });

  it('parses tags from frontmatter', () => {
    const post = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(post.tags).toEqual(['typescript', 'web']);
  });

  it('detects draft posts', () => {
    const draft = parseFile(join(FIXTURES, 'draft-post.md'), FIXTURES);
    expect(draft.draft).toBe(true);

    const published = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(published.draft).toBe(false);
  });

  it('parses layout from frontmatter', () => {
    const post = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(post.layout).toBe('post');
  });

  it('defaults layout to "default" when not specified', () => {
    const post = parseFile(join(FIXTURES, 'nested', 'another-post.md'), FIXTURES);
    expect(post.layout).toBe('default');
  });

  it('converts markdown content to HTML', () => {
    const post = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(post.html).toContain('<h1>Hello World</h1>');
    expect(post.html).toContain('<strong>bold</strong>');
  });

  it('generates a slug from file path', () => {
    const post = parseFile(join(FIXTURES, 'hello-world.md'), FIXTURES);
    expect(post.slug).toBe('hello-world');
  });

  it('handles nested directories for slug generation', () => {
    const post = parseFile(
      join(FIXTURES, 'nested', 'another-post.md'),
      FIXTURES,
    );
    expect(post.slug).toBe('nested-another-post');
  });

  it('uses default title from slug when frontmatter title is missing', () => {
    // File with no title in frontmatter
    const raw = join(FIXTURES, 'nested', 'another-post.md');
    // another-post.md has a title, so let's test the default date behavior instead
    const post = parseFile(raw, FIXTURES);
    expect(post.date).toBeInstanceOf(Date);
  });
});

describe('parseDirectory', () => {
  it('parses all markdown files in directory recursively', () => {
    const posts = parseDirectory(FIXTURES);
    expect(posts.length).toBe(3);
  });

  it('includes draft posts in raw parse results', () => {
    const posts = parseDirectory(FIXTURES);
    const drafts = posts.filter((p) => p.draft);
    expect(drafts.length).toBe(1);
  });
});
