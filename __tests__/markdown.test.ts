import { parseMarkdown, slugify } from '../src/markdown';

describe('slugify', () => {
  it('lowercases and replaces spaces with dashes', () => {
    expect(slugify('My First Post')).toBe('my-first-post');
  });

  it('strips special characters', () => {
    expect(slugify('Hello, World!')).toBe('hello-world');
  });

  it('collapses repeated dashes', () => {
    expect(slugify('A  B---C')).toBe('a-b-c');
  });

  it('falls back to a default for empty input', () => {
    expect(slugify('!!!')).toBe('untitled');
  });
});

describe('parseMarkdown', () => {
  it('parses frontmatter title, date, and tags', () => {
    const page = parseMarkdown(
      [
        '---',
        'title: My First Post',
        'date: 2024-01-15',
        'tags: [typescript, cli]',
        '---',
        '# Hello',
        '',
        'Some **bold** text.',
      ].join('\n'),
      'my-first-post.md'
    );

    expect(page.title).toBe('My First Post');
    expect(page.date).toBe('2024-01-15');
    expect(page.tags).toEqual(['typescript', 'cli']);
    expect(page.html).toContain('<h1>Hello</h1>');
    expect(page.html).toContain('<strong>bold</strong>');
  });

  it('uses the file name as the fallback title', () => {
    const page = parseMarkdown('# Just a heading', 'hello-world.md');
    expect(page.title).toBe('hello-world');
    expect(page.slug).toBe('hello-world');
  });

  it('handles content without frontmatter', () => {
    const page = parseMarkdown('Plain content', 'plain.md');
    expect(page.html).toContain('Plain content');
    expect(page.tags).toEqual([]);
    expect(page.date).toBeUndefined();
  });

  it('uses a frontmatter slug when provided', () => {
    const page = parseMarkdown(
      ['---', 'title: Weird Title', 'slug: custom-slug', '---', 'Body'].join('\n'),
      'weird.md'
    );
    expect(page.slug).toBe('custom-slug');
  });

  it('builds a text excerpt from the rendered html', () => {
    const page = parseMarkdown('# T\n\nSome <b>important</b> words.', 'x.md');
    expect(page.excerpt).toBe('T Some important words.');
  });
});
