import { parseMarkdown } from '../src/frontmatter';

describe('parseMarkdown', () => {
  it('returns empty data and unchanged content when there is no frontmatter', () => {
    const raw = '# Hello\n\nWorld';
    const result = parseMarkdown(raw);
    expect(result.data).toEqual({});
    expect(result.content).toBe(raw);
  });

  it('strips a YAML frontmatter block and parses its data', () => {
    const raw = [
      '---',
      'title: My Post',
      'date: 2024-01-02',
      'tags:',
      '  - typescript',
      '  - ssg',
      '---',
      '# Body',
    ].join('\n');

    const result = parseMarkdown(raw);

    expect(result.data).toEqual({
      title: 'My Post',
      date: new Date('2024-01-02'),
      tags: ['typescript', 'ssg'],
    });
    expect(result.content).toBe('# Body');
  });

  it('handles CRLF line endings in the delimiter', () => {
    const raw = '---\r\ntitle: Hello\r\n---\r\nBody';
    const result = parseMarkdown(raw);
    expect(result.data).toEqual({ title: 'Hello' });
    expect(result.content).toBe('Body');
  });

  it('handles comma-separated tag strings', () => {
    const raw = '---\ntitle: T\ntags: a, b, c\n---\nBody';
    const result = parseMarkdown(raw);
    expect(result.data.tags).toBe('a, b, c');
  });

  it('does not treat a leading thematic break as frontmatter when no closing delimiter exists', () => {
    const raw = '---\n# Just a heading\n\nSome text';
    const result = parseMarkdown(raw);
    expect(result.data).toEqual({});
    expect(result.content).toBe(raw);
  });

  it('strips a UTF-8 BOM before looking for frontmatter', () => {
    const raw = '\uFEFF---\ntitle: With BOM\n---\nBody';
    const result = parseMarkdown(raw);
    expect(result.data).toEqual({ title: 'With BOM' });
    expect(result.content).toBe('Body');
  });

  it('leaves the body content intact after stripping', () => {
    const raw = '---\ntitle: Post\n---\n\n## Section\n\nSome **bold** text';
    const result = parseMarkdown(raw);
    expect(result.content).toBe('\n## Section\n\nSome **bold** text');
  });
});
