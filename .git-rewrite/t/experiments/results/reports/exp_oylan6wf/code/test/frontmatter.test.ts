import { describe, expect, it } from 'vitest';
import { parseFrontmatter } from '../src/frontmatter.js';

describe('parseFrontmatter', () => {
  it('parses title, date, tags, draft', () => {
    const { frontmatter, body } = parseFrontmatter(
      `---
title: Hello World
date: 2024-03-15
tags: [ts, blog]
draft: true
---
Body text.`,
    );
    expect(frontmatter.title).toBe('Hello World');
    expect(frontmatter.date).toBeInstanceOf(Date);
    expect(frontmatter.date!.toISOString()).toMatch(/^2024-03-15/);
    expect(frontmatter.tags).toEqual(['ts', 'blog']);
    expect(frontmatter.draft).toBe(true);
    expect(body.trim()).toBe('Body text.');
  });

  it('applies defaults when frontmatter is absent', () => {
    const { frontmatter, body } = parseFrontmatter('# Just markdown', 'fallback-title');
    expect(frontmatter.title).toBe('fallback-title');
    expect(frontmatter.date).toBeNull();
    expect(frontmatter.tags).toEqual([]);
    expect(frontmatter.draft).toBe(false);
    expect(body).toBe('# Just markdown');
  });

  it('normalizes comma-separated string tags and dedupes', () => {
    const { frontmatter } = parseFrontmatter(`---
tags: a, b , a
---
x`);
    expect(frontmatter.tags).toEqual(['a', 'b']);
  });

  it('handles YAML list tags with extra whitespace', () => {
    const { frontmatter } = parseFrontmatter(`---
tags:
  - alpha
  - beta
---
x`);
    expect(frontmatter.tags).toEqual(['alpha', 'beta']);
  });

  it('treats invalid dates as null', () => {
    const { frontmatter } = parseFrontmatter(`---
date: not-a-date
---
x`);
    expect(frontmatter.date).toBeNull();
  });

  it('treats draft: "true" string as true, other values as false', () => {
    expect(parseFrontmatter('---\ndraft: "true"\n---\nx').frontmatter.draft).toBe(true);
    expect(parseFrontmatter('---\ndraft: false\n---\nx').frontmatter.draft).toBe(false);
    expect(parseFrontmatter('---\ndraft: nope\n---\nx').frontmatter.draft).toBe(false);
  });

  it('passes through custom keys', () => {
    const { frontmatter } = parseFrontmatter(`---
author: Ada
layout: post
---
x`);
    expect(frontmatter.author).toBe('Ada');
    expect(frontmatter.layout).toBe('post');
  });
});
