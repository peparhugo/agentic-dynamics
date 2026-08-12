import { parseFrontmatter, extractTags } from '../src/frontmatter';

describe('parseFrontmatter', () => {
  it('parses title, date, and tags from YAML frontmatter', () => {
    const md = [
      '---',
      'title: Hello World',
      'date: 2024-01-15',
      'tags:',
      '  - intro',
      '  - guide',
      '---',
      '# Body'
    ].join('\n');

    const { content, data } = parseFrontmatter(md);
    expect(data.title).toBe('Hello World');
    expect(data.date).toBeInstanceOf(Date);
    expect((data.date as Date).toISOString().slice(0, 10)).toBe('2024-01-15');
    expect(data.tags).toEqual(['intro', 'guide']);
    expect(content).toContain('# Body');
  });

  it('returns empty data and full content when no frontmatter present', () => {
    const { content, data } = parseFrontmatter('just some text');
    expect(data).toEqual({});
    expect(content).toBe('just some text');
  });

  it('handles inline array tags', () => {
    const { data } = parseFrontmatter('---\ntags: [a, b]\n---\nbody');
    expect(data.tags).toEqual(['a', 'b']);
  });
});

describe('extractTags', () => {
  it('returns only string tags', () => {
    expect(extractTags({ tags: ['x', 5, 'y'] })).toEqual(['x', 'y']);
  });

  it('returns empty array when tags missing or malformed', () => {
    expect(extractTags({})).toEqual([]);
    expect(extractTags({ tags: 'nope' })).toEqual([]);
  });
});
