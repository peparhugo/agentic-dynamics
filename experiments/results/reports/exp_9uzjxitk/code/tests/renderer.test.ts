import { describe, it, expect, beforeEach } from 'vitest';
import { loadTemplates, renderPage } from '../src/renderer.js';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { TemplateContext, Post, Frontmatter } from '../src/types.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const templatesDir = path.join(__dirname, 'fixtures', 'templates');

function makePost(overrides: Partial<Frontmatter> & { slug?: string; html?: string } = {}): Post {
  return {
    slug: overrides.slug || 'test-post',
    frontmatter: {
      title: overrides.title || 'Test Post',
      date: overrides.date || '2024-01-01',
      tags: overrides.tags || [],
      draft: overrides.draft ?? false,
      layout: overrides.layout || 'default',
    },
    raw: '',
    html: overrides.html || '<p>Test content</p>',
    body: '',
  };
}

const siteContext = {
  title: 'Test Site',
  posts: [],
  tags: [],
  site: { title: 'Test Site', description: 'A test site', baseUrl: 'http://localhost:8080' },
};

describe('renderer', () => {
  let templates: ReturnType<typeof loadTemplates>;

  beforeEach(() => {
    templates = loadTemplates(templatesDir);
  });

  it('loads page templates', () => {
    expect(Object.keys(templates.pages)).toContain('index');
    expect(Object.keys(templates.pages)).toContain('post');
    expect(Object.keys(templates.pages)).toContain('tag');
  });

  it('loads layout templates', () => {
    expect(Object.keys(templates.layouts)).toContain('default');
  });

  it('loads partials', () => {
    const postTemplate = templates.pages['post'];
    const post = makePost({ title: 'My Post' });
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).toContain('My Post');
  });

  it('renders post with layout', () => {
    const post = makePost({ title: 'Layout Test' });
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('Layout Test');
    expect(html).toContain('<article>');
  });

  it('renders index page', () => {
    const posts = [
      makePost({ title: 'Post 1', slug: 'post-1' }),
      makePost({ title: 'Post 2', slug: 'post-2' }),
    ];
    const ctx: TemplateContext = { ...siteContext, posts };
    const html = renderPage(templates, 'index', ctx);
    expect(html).toContain('Post 1');
    expect(html).toContain('Post 2');
    expect(html).toContain('post-1.html');
  });

  it('renders tag page', () => {
    const posts = [makePost({ title: 'Tagged Post', slug: 'tagged' })];
    const ctx: TemplateContext = { ...siteContext, posts, title: 'Posts tagged "js"' };
    const html = renderPage(templates, 'tag', ctx);
    expect(html).toContain('Tagged Post');
    expect(html).toContain('tagged.html');
  });

  it('includes partials in rendered output', () => {
    const post = makePost();
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).toContain('Home');
    expect(html).toContain('<nav>');
  });

  it('renders date with dateFormat helper', () => {
    const post = makePost({ date: '2024-01-15' });
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).toContain('January 15, 2024');
  });

  it('renders tags list when present', () => {
    const post = makePost({ tags: ['javascript', 'typescript'] });
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).toContain('href="http://localhost:8080/tags/javascript/"');
    expect(html).toContain('href="http://localhost:8080/tags/typescript/"');
  });

  it('omits tags list when no tags', () => {
    const post = makePost({ tags: [] });
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).not.toContain('<ul class="tags">');
  });

  it('renders post HTML content inside layout', () => {
    const post = makePost({ html: '<p><strong>Bold</strong> content</p>' });
    const ctx: TemplateContext = { ...siteContext, posts: [post], page: post };
    const html = renderPage(templates, 'post', ctx);
    expect(html).toContain('<strong>Bold</strong>');
  });

  it('throws for missing template', () => {
    expect(() => {
      const post = makePost();
      renderPage(templates, 'nonexistent', { ...siteContext, page: post });
    }).toThrow('Template "nonexistent" not found');
  });
});
