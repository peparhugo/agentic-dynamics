import { parseFrontmatter, parseYamlBlock } from '../src/frontmatter';

describe('parseYamlBlock', () => {
  it('parses simple key: value pairs', () => {
    const result = parseYamlBlock('title: Hello\nsubtitle: A story\n');
    expect(result).toEqual({ title: 'Hello', subtitle: 'A story' });
  });

  it('parses quoted values and strips the quotes', () => {
    const result = parseYamlBlock('title: "Hello: World"\nsubtitle: \'Quoted\'\n');
    expect(result).toEqual({ title: 'Hello: World', subtitle: 'Quoted' });
  });

  it('parses booleans and numbers', () => {
    const result = parseYamlBlock('published: true\nfeatured: false\ncount: 42\n');
    expect(result).toEqual({ published: true, featured: false, count: 42 });
  });

  it('parses inline flow-style lists', () => {
    const result = parseYamlBlock('tags: [one, "two", three]\n');
    expect(result).toEqual({ tags: ['one', 'two', 'three'] });
  });

  it('ignores comments and blank lines', () => {
    const result = parseYamlBlock('# a comment\n\n title: X\n');
    expect(result).toEqual({ title: 'X' });
  });

  it('returns an empty object for an empty block', () => {
    expect(parseYamlBlock('')).toEqual({});
  });
});

describe('parseFrontmatter', () => {
  it('parses YAML frontmatter and strips it from the content', () => {
    const markdown = [
      '---',
      'title: My Page',
      'date: 2024-05-01',
      'tags: [a, b]',
      '---',
      '',
      '# Heading',
      '',
      'Body text.',
      '',
    ].join('\n');
    const { data, content } = parseFrontmatter(markdown);
    expect(data.title).toBe('My Page');
    expect(data.date).toBe('2024-05-01');
    expect(data.tags).toEqual(['a', 'b']);
    expect(content).toContain('# Heading');
    expect(content).toContain('Body text.');
    expect(content).not.toContain('title:');
  });

  it('handles markdown with no frontmatter', () => {
    const markdown = '# Just content\n';
    const { data, content } = parseFrontmatter(markdown);
    expect(data).toEqual({});
    expect(content).toBe(markdown);
  });

  it('merges YAML data on top of gray-matter output', () => {
    const markdown = ['---', 'title: YAML Title', 'tags: [x]', '---', '', 'Body'].join('\n');
    const { data } = parseFrontmatter(markdown);
    expect(data.title).toBe('YAML Title');
    expect(data.tags).toEqual(['x']);
  });

  it('parses JSON frontmatter via gray-matter', () => {
    const markdown = ['---json', '{"title": "JSON Title", "date": "2024-01-01"}', '---', '', 'Body'].join(
      '\n'
    );
    const { data, content } = parseFrontmatter(markdown);
    expect(data.title).toBe('JSON Title');
    expect(data.date).toBe('2024-01-01');
    expect(content).toContain('Body');
  });

  it('does not treat a lone --- paragraph as frontmatter', () => {
    const markdown = '---\n\nJust a horizontal rule.';
    const { data, content } = parseFrontmatter(markdown);
    expect(data).toEqual({});
    expect(content).toBe(markdown);
  });

  it('handles a BOM at the start of the file', () => {
    const markdown = ['\uFEFF---', 'title: Bom', '---', '', 'Body'].join('\n');
    const { data, content } = parseFrontmatter(markdown);
    expect(data.title).toBe('Bom');
    expect(content).toContain('Body');
  });
});
