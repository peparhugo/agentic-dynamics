import { markdownToHtml, slugify, parsePage } from '../src/markdown';

describe('markdownToHtml', () => {
  it('converts headings and paragraphs to HTML', () => {
    const html = markdownToHtml('# Title\n\nSome **bold** text.');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<p>Some');
  });

  it('converts links', () => {
    const html = markdownToHtml('[example](https://example.com)');
    expect(html).toContain('<a href="https://example.com">example</a>');
  });

  it('converts lists', () => {
    const html = markdownToHtml('- one\n- two');
    expect(html).toContain('<li>one</li>');
    expect(html).toContain('<li>two</li>');
  });
});

describe('slugify', () => {
  it('lowercases and dasherizes file names', () => {
    expect(slugify('Hello World.md')).toBe('hello-world');
  });

  it('strips the .md extension', () => {
    expect(slugify('About.md')).toBe('about');
  });

  it('falls back to a default for empty input', () => {
    expect(slugify('!!!')).toBe('untitled');
  });
});

describe('parsePage', () => {
  it('builds a page with frontmatter and html content', () => {
    const page = parsePage(
      'hello.md',
      '---\ntitle: Hello\n---\n\n# Welcome'
    );
    expect(page.slug).toBe('hello');
    expect(page.title).toBe('Hello');
    expect(page.tags).toEqual([]);
    expect(page.contentHtml).toContain('<h1>Welcome</h1>');
  });

  it('uses the slug as title when title is missing', () => {
    const page = parsePage('no-title.md', '# Just body');
    expect(page.title).toBe('no-title');
  });

  it('captures tags and date', () => {
    const page = parsePage(
      'post.md',
      '---\ntitle: Post\ndate: 2024-02-02\ntags: [news, tech]\n---\nbody'
    );
    expect(page.date).toBe('2024-02-02');
    expect(page.tags).toEqual(['news', 'tech']);
  });
});
