import { describe, it, expect } from 'vitest';
import { parseFrontMatter } from '../src/builder';

describe('frontmatter parsing', () => {
  it('parses basic fields', () => {
    const md = `---\n title: Hello \n date: 2024-01-02 \n tags: [a, b] \n draft: true \n layout: post \n---\nContent`;
    const { content, data } = parseFrontMatter(md);
    expect(content.trim()).toBe('Content');
    expect(data.title).toBe('Hello');
    const iso = new Date(String(data.date)).toISOString();
    expect(iso.startsWith('2024-01-02')).toBe(true);
    expect(data.tags).toEqual(['a', 'b']);
    expect(data.draft).toBe(true);
    expect(data.layout).toBe('post');
  });

  it('parses tags as comma-separated string', () => {
    const md = `---\n title: Test \n tags: a, b , c\n---\nHi`;
    const { data } = parseFrontMatter(md);
    expect(data.tags).toBe('a, b , c');
  });
});
