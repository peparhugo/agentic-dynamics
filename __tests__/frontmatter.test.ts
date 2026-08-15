import { extractFrontmatterBlock, parseFrontmatter, parseYamlBlock } from '../src/frontmatter';

describe('extractFrontmatterBlock', () => {
  it('extracts a YAML block delimited by ---', () => {
    const raw = '---\ntitle: Hello\ndate: 2024-01-02\n---\n# Body';
    expect(extractFrontmatterBlock(raw)).toBe('title: Hello\ndate: 2024-01-02');
  });

  it('returns null when the file has no frontmatter', () => {
    expect(extractFrontmatterBlock('# Just a heading')).toBeNull();
  });

  it('returns null when there is no closing delimiter', () => {
    expect(extractFrontmatterBlock('---\ntitle: Hello\n# Body')).toBeNull();
  });
});

describe('parseYamlBlock', () => {
  it('parses scalar values', () => {
    const data = parseYamlBlock('title: My Title\ndate: 2024-01-02');
    expect(data.title).toBe('My Title');
    expect(data.date).toBe('2024-01-02');
  });

  it('parses booleans and numbers', () => {
    const data = parseYamlBlock('draft: true\nrating: 5\npi: 3.14');
    expect(data.draft).toBe(true);
    expect(data.rating).toBe(5);
    expect(data.pi).toBe(3.14);
  });

  it('parses comma-separated lists', () => {
    const data = parseYamlBlock('tags: a, b, c');
    expect(data.tags).toEqual(['a', 'b', 'c']);
  });

  it('parses bracket lists', () => {
    const data = parseYamlBlock('tags: [a, b]');
    expect(data.tags).toEqual(['a', 'b']);
  });

  it('strips surrounding quotes', () => {
    const data = parseYamlBlock('title: "Quoted"\nsubtitle: \'Single\'');
    expect(data.title).toBe('Quoted');
    expect(data.subtitle).toBe('Single');
  });

  it('skips blank lines and comments', () => {
    const data = parseYamlBlock('# comment\ntitle: Hello\n\n');
    expect(data.title).toBe('Hello');
  });
});

describe('parseFrontmatter', () => {
  it('parses frontmatter from a full markdown source', () => {
    const source = '---\ntitle: Welcome\ndate: 2024-03-01\ntags: intro, hello\n---\n# Body';
    const data = parseFrontmatter(source);
    expect(data.title).toBe('Welcome');
    expect(data.date).toBe('2024-03-01');
    expect(data.tags).toEqual(['intro', 'hello']);
  });

  it('returns an empty object when there is no frontmatter', () => {
    expect(parseFrontmatter('# No frontmatter')).toEqual({});
  });
});
