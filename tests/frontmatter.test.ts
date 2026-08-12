import { parseFrontmatter } from '../src/frontmatter';

describe('parseFrontmatter', () => {
  it('parses title, date and tags', () => {
    const source = [
      '---',
      'title: My First Post',
      'date: 2024-03-01',
      'tags:',
      '  - javascript',
      '  - typescript',
      '---',
      '# Body',
      '',
      'Some **content**.',
    ].join('\n');

    const { data, content } = parseFrontmatter(source);

    expect(data.title).toBe('My First Post');
    expect(data.date).toBe('2024-03-01');
    expect(data.tags).toEqual(['javascript', 'typescript']);
    expect(content).toContain('# Body');
    expect(content).toContain('Some **content**.');
    expect(content).not.toContain('title:');
  });

  it('returns the whole string as content when there is no frontmatter', () => {
    const { data, content } = parseFrontmatter('# No metadata here');
    expect(data).toEqual({});
    expect(content).toBe('# No metadata here');
  });

  it('keeps the raw content body intact', () => {
    const { content } = parseFrontmatter('---\ntitle: Only Title\n---\n\nThis is the body.\n');
    expect(content).toBe('\nThis is the body.\n');
  });

  it('omits empty data fields', () => {
    const { data } = parseFrontmatter('---\n---\n# Nothing');
    expect(data).toEqual({});
  });

  it('parses template and layout fields', () => {
    const { data } = parseFrontmatter('---\ntitle: T\ntemplate: post\nlayout: wide\n---\n# Body');
    expect(data.template).toBe('post');
    expect(data.layout).toBe('wide');
  });

  it('keeps arbitrary custom fields for templates', () => {
    const { data } = parseFrontmatter('---\ntitle: T\nauthor: Ada\ncount: 3\n---\n# Body');
    expect(data.author).toBe('Ada');
    expect(data.count).toBe(3);
  });
});
