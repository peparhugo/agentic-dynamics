import { buildIndexHtml, buildPageHtml, pageTitle } from '../src/generator';
import type { Page } from '../src/types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'post',
    sourcePath: 'post.md',
    data: {},
    body: '# Hello',
    html: '<h1>Hello</h1>',
    outputFile: 'post.html',
    ...overrides,
  };
}

describe('pageTitle', () => {
  it('uses the frontmatter title when present', () => {
    expect(pageTitle({ title: 'My Post' }, 'post')).toBe('My Post');
  });

  it('falls back to the slug when no title is present', () => {
    expect(pageTitle({}, 'post')).toBe('post');
  });

  it('ignores whitespace-only titles', () => {
    expect(pageTitle({ title: '   ' }, 'post')).toBe('post');
  });
});

describe('buildPageHtml', () => {
  it('produces a complete self-contained HTML document', () => {
    const html = buildPageHtml(
      makePage({
        data: { title: 'About Me', date: '2024-03-01', tags: ['meta', 'intro'] },
        html: '<p>Hello there</p>',
      }),
    );

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>About Me</title>');
    expect(html).toContain('<h1 class="title">About Me</h1>');
    expect(html).toContain('<span class="date">2024-03-01</span>');
    expect(html).toContain('<span class="tag">meta</span>');
    expect(html).toContain('<span class="tag">intro</span>');
    expect(html).toContain('<p>Hello there</p>');
    expect(html).toContain('<style>');
    expect(html).toContain('</style>');
    expect(html).toContain('<a class="back" href="./index.html">');
  });

  it('falls back to the slug in the <title> when no title is set', () => {
    const html = buildPageHtml(makePage({ data: {}, html: '<p>body</p>' }));
    expect(html).toContain('<title>post</title>');
  });

  it('does not emit metadata when none is present', () => {
    const html = buildPageHtml(makePage({ data: {}, html: '<p>body</p>' }));
    expect(html).not.toContain('<p class="meta">');
  });

  it('escapes HTML in the title', () => {
    const html = buildPageHtml(makePage({ data: { title: '<script>alert(1)</script>' } }));
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
  });
});

describe('buildIndexHtml', () => {
  const pages: Page[] = [
    makePage({
      slug: 'about',
      outputFile: 'about.html',
      data: { title: 'About', date: '2024-01-01' },
    }),
    makePage({
      slug: 'blog',
      outputFile: 'blog.html',
      data: { title: 'Blog', tags: ['news'] },
    }),
    makePage({ slug: 'plain', outputFile: 'plain.html', data: {} }),
  ];

  it('lists every page with a link to its output file', () => {
    const html = buildIndexHtml(pages);

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>All pages</title>');
    expect(html).toContain('<a href="./about.html"><h2 class="entry-title">About</h2></a>');
    expect(html).toContain('<a href="./blog.html"><h2 class="entry-title">Blog</h2></a>');
    expect(html).toContain('<a href="./plain.html"><h2 class="entry-title">plain</h2></a>');
    expect(html).toContain('<span class="date">2024-01-01</span>');
    expect(html).toContain('<span class="tag">news</span>');
  });

  it('produces an empty list for no pages', () => {
    const html = buildIndexHtml([]);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<ul class="page-list">');
  });
});
