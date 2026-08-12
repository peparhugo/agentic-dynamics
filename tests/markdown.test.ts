import { parseMarkdown } from '../src/markdown';

describe('parseMarkdown', () => {
  it('converts markdown body to HTML', () => {
    const result = parseMarkdown('---\ntitle: Hello\n---\n\n# Heading\n\nSome **bold** text.');
    expect(result.contentHtml).toContain('<h1>Heading</h1>');
    expect(result.contentHtml).toContain('<strong>bold</strong>');
  });

  it('extracts title, date and tags from frontmatter', () => {
    const result = parseMarkdown(
      '---\ntitle: My Post\ndate: 2024-05-01\ntags: [typescript, node]\n---\n\nBody.'
    );
    expect(result.frontmatter.title).toBe('My Post');
    expect(result.frontmatter.tags).toEqual(['typescript', 'node']);
    expect(result.frontmatter.date).not.toBeUndefined();
  });

  it('treats a YAML date as a valid date string', () => {
    const result = parseMarkdown('---\ndate: 2024-05-01\n---\n\nBody.');
    expect(result.frontmatter.date).toBeDefined();
  });

  it('parses comma-separated tags as an array', () => {
    const result = parseMarkdown('---\ntags: one, two\n---\n\nBody.');
    expect(result.frontmatter.tags).toEqual(['one', 'two']);
  });

  it('returns empty defaults when frontmatter is missing', () => {
    const result = parseMarkdown('# Just a heading');
    expect(result.frontmatter.title).toBeUndefined();
    expect(result.frontmatter.date).toBeUndefined();
    expect(result.frontmatter.tags).toBeUndefined();
    expect(result.contentHtml).toContain('<h1>Just a heading</h1>');
  });
});
