import { describe, it, expect } from 'vitest';
import { parse } from '../src/parser.js';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.join(__dirname, 'fixtures', 'posts');

describe('parse', () => {
  it('parses frontmatter title', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.frontmatter.title).toBe('Hello World');
  });

  it('parses frontmatter date', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.frontmatter.date).toBe('2024-01-15');
  });

  it('parses frontmatter tags', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.frontmatter.tags).toEqual(['javascript', 'tutorial']);
  });

  it('parses draft flag as false by default', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.frontmatter.draft).toBe(false);
  });

  it('parses draft flag as true', () => {
    const result = parse(path.join(fixtures, 'post2.md'));
    expect(result.frontmatter.draft).toBe(true);
  });

  it('converts markdown to HTML', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.html).toContain('<h2>Getting Started</h2>');
  });

  it('applies syntax highlighting to code blocks', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.html).toContain('class="hljs');
    expect(result.html).toContain('language-javascript');
  });

  it('uses plaintext for unknown languages', () => {
    const result = parse(path.join(fixtures, 'post3.md'));
    expect(result.html).toContain('language-plaintext');
  });

  it('handles missing frontmatter with defaults', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.frontmatter.layout).toBe('default');
  });

  it('handles string tags converted to array', () => {
    const result = parse(path.join(fixtures, 'post3.md'));
    expect(result.frontmatter.tags).toEqual(['typescript', 'javascript']);
  });

  it('handles posts with no tags', () => {
    const result = parse(path.join(fixtures, 'post2.md'));
    expect(result.frontmatter.tags).toEqual(['typescript']);
  });

  it('generates raw markdown content', () => {
    const result = parse(path.join(fixtures, 'post1.md'));
    expect(result.raw).toContain('## Getting Started');
    expect(result.raw).not.toContain('---');
  });
});
