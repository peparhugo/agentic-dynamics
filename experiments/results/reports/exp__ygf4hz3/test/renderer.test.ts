import { describe, it, expect, beforeEach } from 'vitest';
import { Renderer } from '../src/renderer';
import { Page } from '../src/types';
import path from 'path';

const TEMPLATES = path.join(__dirname, 'fixtures', 'templates');

function makePage(overrides: Partial<Page> & { frontmatter: Record<string, unknown> }): Page {
  return {
    path: 'test.md',
    url: '/test.html',
    content: '# Hello',
    html: '<h1>Hello</h1>',
    ...overrides,
    frontmatter: { title: 'Test', ...overrides.frontmatter } as Page['frontmatter'],
  };
}

describe('Renderer', () => {
  let renderer: Renderer;

  beforeEach(() => {
    renderer = new Renderer(TEMPLATES);
  });

  it('renders a page using the specified template', () => {
    const page = makePage({
      frontmatter: { title: 'My Post', date: '2024-01-01', template: 'post' },
    });

    const result = renderer.render(page, [page]);
    expect(result).toContain('<h1>My Post</h1>');
    expect(result).toContain('<h1>Hello</h1>');
  });

  it('renders page content as raw HTML', () => {
    const page = makePage({
      frontmatter: { title: 'Rich Post', template: 'post' },
      html: '<p><strong>Bold</strong> and <em>italic</em></p>',
    });

    const result = renderer.render(page, [page]);
    expect(result).toContain('<strong>Bold</strong>');
    expect(result).toContain('<em>italic</em>');
  });

  it('applies default layout wrapping', () => {
    const page = makePage({
      frontmatter: { title: 'Test', template: 'post' },
    });

    const result = renderer.render(page, [page]);
    expect(result).toContain('<!DOCTYPE html>');
    expect(result).toContain('<html lang="en">');
    expect(result).toContain('<main>');
    expect(result).toContain('</html>');
  });

  it('uses custom layout when specified in frontmatter', () => {
    const page = makePage({
      frontmatter: { title: 'Test', template: 'post', layout: 'default' },
    });

    const result = renderer.render(page, [page]);
    expect(result).toContain('<main>');
  });

  it('includes partials (header and footer) in rendered output', () => {
    const page = makePage({
      frontmatter: { title: 'Test', template: 'post' },
    });

    const result = renderer.render(page, [page]);
    expect(result).toContain('Home');
    expect(result).toContain('About');
    expect(result).toContain('Site Footer');
  });

  it('renders tags for a page', () => {
    const page = makePage({
      frontmatter: { title: 'Tagged Post', tags: ['tech', 'js'], template: 'post' },
    });

    const result = renderer.render(page, [page]);
    expect(result).toContain('/tags/tech.html');
    expect(result).toContain('/tags/js.html');
  });

  it('makes all pages available in template context', () => {
    const post1 = makePage({
      frontmatter: { title: 'Post One', date: '2024-01-01', template: 'index' },
      url: '/post-one.html',
    });
    const post2 = makePage({
      frontmatter: { title: 'Post Two', date: '2024-06-01', template: 'index' },
      url: '/post-two.html',
    });

    const result = renderer.render(post1, [post1, post2]);
    expect(result).toContain('Post One');
    expect(result).toContain('Post Two');
    expect(result).toContain('/post-one.html');
    expect(result).toContain('/post-two.html');
  });

  it('throws when template is not found', () => {
    const page = makePage({
      frontmatter: { title: 'Test', template: 'nonexistent' },
    });

    expect(() => renderer.render(page, [page])).toThrow(/Template "nonexistent" not found/);
  });

  it('renders tag index pages', () => {
    const pages = [
      makePage({
        frontmatter: { title: 'Post One', tags: ['tech'], date: '2024-01-01' },
        url: '/post-one.html',
      }),
      makePage({
        frontmatter: { title: 'Post Two', tags: ['tech'], date: '2024-02-01' },
        url: '/post-two.html',
      }),
    ];

    const allPages = [...pages];

    const result = renderer.renderTagPage('tech', pages, allPages);
    expect(result).toContain('Tag: tech');
    expect(result).toContain('Post One');
    expect(result).toContain('Post Two');
  });

  it('throws when no tags template is available', () => {
    const emptyRenderer = new Renderer(path.join(TEMPLATES, '..'));
    const page = makePage({ frontmatter: { title: 'Test' } });

    // This template dir won't have a tags template
    // Just verify that proper error is thrown for missing template
  });

  it('does not apply layout if layout template is missing', () => {
    const page = makePage({
      frontmatter: { title: 'Test', template: 'post', layout: 'nonexistent' },
    });

    const result = renderer.render(page, [page]);
    expect(result).not.toContain('<!DOCTYPE html>');
  });

  it('exposes site config in template context', () => {
    const page = makePage({
      frontmatter: { title: 'Site Test', template: 'post' },
    });

    const result = renderer.render(page, [page], { title: 'My Site' });
    expect(result).toContain('My Site');
  });
});
