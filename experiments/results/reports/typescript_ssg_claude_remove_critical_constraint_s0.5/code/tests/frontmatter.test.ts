import { describe, it, expect } from 'vitest';
import { parseDocument, normalizeTags, normalizeDate, slugify } from '../src/frontmatter.js';

describe('parseDocument', () => {
  it('parses full frontmatter', () => {
    const { frontmatter, body } = parseDocument(
      [
        '---',
        'title: My Post',
        'date: 2026-01-15',
        'tags: [a, b]',
        'draft: true',
        'layout: post',
        'description: Hi',
        '---',
        '',
        'Body text.',
      ].join('\n'),
    );
    expect(frontmatter.title).toBe('My Post');
    expect(frontmatter.date?.toISOString()).toBe('2026-01-15T00:00:00.000Z');
    expect(frontmatter.tags).toEqual(['a', 'b']);
    expect(frontmatter.draft).toBe(true);
    expect(frontmatter.layout).toBe('post');
    expect(frontmatter.description).toBe('Hi');
    expect(body.trim()).toBe('Body text.');
  });

  it('applies defaults when frontmatter is absent', () => {
    const { frontmatter, body } = parseDocument('Just text.', 'my-file');
    expect(frontmatter.title).toBe('my-file');
    expect(frontmatter.date).toBeNull();
    expect(frontmatter.tags).toEqual([]);
    expect(frontmatter.draft).toBe(false);
    expect(frontmatter.layout).toBe('default');
    expect(body).toBe('Just text.');
  });

  it('treats non-true draft values as false', () => {
    const { frontmatter } = parseDocument('---\ndraft: "yes"\n---\nx');
    expect(frontmatter.draft).toBe(false);
  });

  it('passes through extra keys and slugifies slug', () => {
    const { frontmatter } = parseDocument('---\nauthor: Ada\nslug: My Fancy Slug!\n---\nx');
    expect(frontmatter.author).toBe('Ada');
    expect(frontmatter.slug).toBe('my-fancy-slug');
  });
});

describe('normalizeTags', () => {
  it('accepts arrays', () => {
    expect(normalizeTags(['a', 'b'])).toEqual(['a', 'b']);
  });
  it('accepts comma-separated strings', () => {
    expect(normalizeTags('a, b , c')).toEqual(['a', 'b', 'c']);
  });
  it('dedupes case-insensitively and drops empties', () => {
    expect(normalizeTags(['TS', 'ts', '', '  '])).toEqual(['TS']);
  });
  it('returns [] for missing/invalid values', () => {
    expect(normalizeTags(undefined)).toEqual([]);
    expect(normalizeTags(42)).toEqual([]);
  });
});

describe('normalizeDate', () => {
  it('accepts Date, string, and rejects invalid', () => {
    expect(normalizeDate(new Date('2026-01-01'))?.getUTCFullYear()).toBe(2026);
    expect(normalizeDate('2026-06-01')?.getUTCMonth()).toBe(5);
    expect(normalizeDate('not a date')).toBeNull();
    expect(normalizeDate(undefined)).toBeNull();
  });
});

describe('slugify', () => {
  it('lowercases, strips diacritics and symbols', () => {
    expect(slugify('Héllo, Wörld!')).toBe('hello-world');
    expect(slugify('  --A  B--  ')).toBe('a-b');
  });
});
