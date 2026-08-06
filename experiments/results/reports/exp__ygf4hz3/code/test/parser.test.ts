import { describe, it, expect } from 'vitest';
import { parseMarkdownFile, parseAllMarkdown } from '../src/parser';
import path from 'path';

const FIXTURES = path.join(__dirname, 'fixtures', 'source');

describe('parseMarkdownFile', () => {
  it('parses frontmatter title', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.frontmatter.title).toBe('First Post');
  });

  it('parses frontmatter date', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.frontmatter.date).toBe('2024-01-15');
  });

  it('parses frontmatter tags as array', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.frontmatter.tags).toEqual(['tech', 'javascript']);
  });

  it('parses draft flag', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'draft-post.md'), FIXTURES);
    expect(page.frontmatter.draft).toBe(true);
  });

  it('parses template field', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.frontmatter.template).toBe('post');
  });

  it('converts markdown to HTML', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.html).toContain('<h1>First Post</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
  });

  it('generates correct URL from file path', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.url).toBe('/post-one.html');
  });

  it('preserves raw markdown content', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-one.md'), FIXTURES);
    expect(page.content).toContain('# First Post');
    expect(page.content).toContain('**bold**');
  });

  it('assigns title from filename when not in frontmatter', () => {
    const filePath = path.join(FIXTURES, 'post-two.md');
    const page = parseMarkdownFile(filePath, FIXTURES);
    expect(page.frontmatter.title).toBe('Second Post');
  });

  it('highlights code blocks', () => {
    const page = parseMarkdownFile(path.join(FIXTURES, 'post-two.md'), FIXTURES);
    expect(page.html).toContain('hljs');
    expect(page.html).toContain('language-javascript');
  });
});

describe('parseAllMarkdown', () => {
  it('finds all markdown files in source directory', () => {
    const pages = parseAllMarkdown(FIXTURES, true);
    expect(pages.length).toBeGreaterThanOrEqual(3);
  });

  it('filters out draft pages when includeDrafts is false', () => {
    const pages = parseAllMarkdown(FIXTURES, false);
    const drafts = pages.filter(p => p.frontmatter.draft);
    expect(drafts.length).toBe(0);
  });

  it('includes draft pages when includeDrafts is true', () => {
    const pages = parseAllMarkdown(FIXTURES, true);
    const drafts = pages.filter(p => p.frontmatter.draft);
    expect(drafts.length).toBe(1);
    expect(drafts[0].frontmatter.title).toBe('Draft Post');
  });

  it('sorts pages by date descending', () => {
    const pages = parseAllMarkdown(FIXTURES, true);
    const dates = pages
      .filter(p => p.frontmatter.date)
      .map(p => new Date(p.frontmatter.date!).getTime());

    expect(dates.length).toBeGreaterThanOrEqual(2);
    for (let i = 1; i < dates.length; i++) {
      expect(dates[i]).toBeLessThanOrEqual(dates[i - 1]);
    }
  });

  it('handles pages without date by placing them at end', () => {
    const pages = parseAllMarkdown(FIXTURES, true);
    const lastPage = pages[pages.length - 1];
    expect(lastPage.frontmatter.date).toBeUndefined();
  });
});
