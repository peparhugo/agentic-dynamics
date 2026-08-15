import { extractYamlBlock, normalizeTags, parseFrontmatter, parseYamlBlock } from '../frontmatter';

describe('parseYamlBlock', () => {
  it('parses scalar key/value pairs', () => {
    const data = parseYamlBlock('title: Hello\ndate: 2026-01-15');
    expect(data.title).toBe('Hello');
    expect(data.date).toBe('2026-01-15');
  });

  it('parses quoted values and strips surrounding quotes', () => {
    const data = parseYamlBlock('title: "Hello World"\nauthor: \'Jane\'');
    expect(data.title).toBe('Hello World');
    expect(data.author).toBe('Jane');
  });

  it('parses numbers and booleans', () => {
    const data = parseYamlBlock('count: 42\nrating: 4.5\npublished: true\nhidden: false');
    expect(data.count).toBe(42);
    expect(data.rating).toBe(4.5);
    expect(data.published).toBe(true);
    expect(data.hidden).toBe(false);
  });

  it('parses inline arrays', () => {
    const data = parseYamlBlock('tags: [a, b, c]');
    expect(data.tags).toEqual(['a', 'b', 'c']);
  });

  it('parses comma separated lists', () => {
    const data = parseYamlBlock('tags: one, two, three');
    expect(data.tags).toEqual(['one', 'two', 'three']);
  });

  it('parses YAML block lists', () => {
    const data = parseYamlBlock('tags:\n  - a\n  - b\n  - c');
    expect(data.tags).toEqual(['a', 'b', 'c']);
  });

  it('skips comments and blank lines', () => {
    const data = parseYamlBlock('# a comment\ntitle: X\n\n\nauthor: Y');
    expect(data.title).toBe('X');
    expect(data.author).toBe('Y');
  });
});

describe('extractYamlBlock', () => {
  it('extracts the block between --- delimiters', () => {
    const source = '---\ntitle: Hi\n---\n# Body';
    expect(extractYamlBlock(source)).toBe('title: Hi');
  });

  it('returns null when there is no frontmatter', () => {
    expect(extractYamlBlock('# Just a heading')).toBeNull();
  });
});

describe('parseFrontmatter', () => {
  it('splits frontmatter from content', () => {
    const source = '---\ntitle: Hello\n---\n# Body text';
    const { data, content } = parseFrontmatter(source);
    expect(data.title).toBe('Hello');
    expect(content).toContain('# Body text');
  });

  it('parses YAML frontmatter with title, date and tags', () => {
    const source = `---
title: My Post
date: 2026-03-10
tags: a, b
---

Body here.`;
    const { data } = parseFrontmatter(source);
    expect(data.title).toBe('My Post');
    expect(data.date).toBe('2026-03-10');
    expect(data.tags).toEqual(['a', 'b']);
  });

  it('merges custom YAML data into gray-matter output', () => {
    const source = '---\nlayout: post\n---\n# Body';
    const { data } = parseFrontmatter(source);
    expect(data.layout).toBe('post');
  });

  it('returns empty data and full content when there is no frontmatter', () => {
    const source = '# Plain markdown\n\nSome text.';
    const { data, content } = parseFrontmatter(source);
    expect(data.title).toBeUndefined();
    expect(content).toBe(source);
  });

  it('normalises tags into arrays in every format', () => {
    const inline = parseFrontmatter('---\ntags: [x, y]\n---\nbody').data.tags;
    const comma = parseFrontmatter('---\ntags: x, y\n---\nbody').data.tags;
    const block = parseFrontmatter('---\ntags:\n  - x\n  - y\n---\nbody').data.tags;
    expect(inline).toEqual(['x', 'y']);
    expect(comma).toEqual(['x', 'y']);
    expect(block).toEqual(['x', 'y']);
  });
});

describe('normalizeTags', () => {
  it('handles arrays, comma strings and unknown values', () => {
    expect(normalizeTags(['a', ' b '])).toEqual(['a', 'b']);
    expect(normalizeTags('a, b, c')).toEqual(['a', 'b', 'c']);
    expect(normalizeTags(undefined)).toEqual([]);
    expect(normalizeTags(42)).toEqual([]);
  });
});
