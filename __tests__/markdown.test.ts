import { parseMarkdown } from '../src/markdown';

describe('parseMarkdown', () => {
  it('converts markdown to HTML', () => {
    const page = parseMarkdown('# Hello World', 'post.md', 'hello-world');
    expect(page.html).toContain('<h1>Hello World</h1>');
  });

  it('reads title, date, and tags from YAML frontmatter', () => {
    const source = [
      '---',
      'title: My Post',
      'date: 2024-05-01',
      'tags: tech, web',
      '---',
      'Body here',
    ].join('\n');
    const page = parseMarkdown(source, 'my-post.md', 'my-post');
    expect(page.title).toBe('My Post');
    expect(page.date).toBe('2024-05-01');
    expect(page.tags).toEqual(['tech', 'web']);
    expect(page.html).toContain('<p>Body here</p>');
  });

  it('falls back to the slug as the title', () => {
    const page = parseMarkdown('# Untitled', 'no-title.md', 'no-title');
    expect(page.title).toBe('no-title');
  });

  it('defaults tags to an empty array', () => {
    const page = parseMarkdown('Just text', 'plain.md', 'plain');
    expect(page.tags).toEqual([]);
  });

  it('merges YAML frontmatter over gray-matter JSON data', () => {
    const source = [
      '---',
      'title: YAML Wins',
      '---',
      'Body',
    ].join('\n');
    const page = parseMarkdown(source, 'yaml.md', 'yaml');
    expect(page.title).toBe('YAML Wins');
  });

  it('sets the source path and slug', () => {
    const page = parseMarkdown('Text', '/tmp/content/a/b.md', 'a-b');
    expect(page.sourcePath).toBe('/tmp/content/a/b.md');
    expect(page.slug).toBe('a-b');
  });

  it('keeps raw content', () => {
    const page = parseMarkdown('**bold**', 'x.md', 'x');
    expect(page.content).toBe('**bold**');
  });
});
