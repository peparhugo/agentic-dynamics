import { parseMarkdownFile, parseYamlFrontmatter } from './frontmatter';

describe('parseYamlFrontmatter', () => {
  it('parses simple key: value pairs', () => {
    const data = parseYamlFrontmatter('title: Hello World\ndate: 2026-01-15');
    expect(data.title).toBe('Hello World');
    expect(data.date).toBe('2026-01-15');
  });

  it('parses bracketed tag arrays', () => {
    const data = parseYamlFrontmatter('tags: [intro, welcome]');
    expect(data.tags).toEqual(['intro', 'welcome']);
  });

  it('parses comma separated tags without brackets', () => {
    const data = parseYamlFrontmatter('tags: intro, welcome');
    expect(data.tags).toEqual(['intro', 'welcome']);
  });

  it('parses a single bare tag into a one element array', () => {
    const data = parseYamlFrontmatter('tags: info');
    expect(data.tags).toEqual(['info']);
  });

  it('strips surrounding quotes from values', () => {
    const data = parseYamlFrontmatter('title: "Quoted Title"');
    expect(data.title).toBe('Quoted Title');
  });

  it('ignores blank lines and comments', () => {
    const data = parseYamlFrontmatter('# comment\n\ntitle: Hello\n');
    expect(data.title).toBe('Hello');
    expect(Object.keys(data)).toEqual(['title']);
  });
});

describe('parseMarkdownFile', () => {
  it('extracts YAML frontmatter and body content', () => {
    const raw = `---
title: Hello World
date: 2026-01-15
tags: [intro, welcome]
---

# Hello World

Body text.
`;
    const { data, content } = parseMarkdownFile(raw);
    expect(data.title).toBe('Hello World');
    expect(data.date).toBe('2026-01-15');
    expect(data.tags).toEqual(['intro', 'welcome']);
    expect(content).toContain('# Hello World');
    expect(content).toContain('Body text.');
    expect(content).not.toContain('---');
  });

  it('handles files with no frontmatter', () => {
    const raw = '# Just a heading\n\nSome text.';
    const { data, content } = parseMarkdownFile(raw);
    expect(data).toEqual({});
    expect(content).toBe(raw);
  });

  it('handles a single bare tag value', () => {
    const raw = `---
title: About
tags: info
---
Content here.
`;
    const { data } = parseMarkdownFile(raw);
    expect(data.tags).toEqual(['info']);
  });
});
