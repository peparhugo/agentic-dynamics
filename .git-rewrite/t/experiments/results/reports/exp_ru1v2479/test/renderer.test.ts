import { describe, it, expect, beforeEach } from 'vitest';
import { join } from 'node:path';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { Renderer } from '../src/renderer';
import { Post, SiteConfig } from '../src/types';

const TEMPLATE_DIR = join(__dirname, 'fixtures', 'templates');

function makeConfig(): SiteConfig {
  return {
    sourceDir: join(__dirname, 'fixtures', 'content'),
    templateDir: TEMPLATE_DIR,
    outputDir: join(__dirname, 'fixtures', 'output'),
    siteTitle: 'Test Site',
    siteUrl: 'http://example.com',
    postsPerPage: 10,
    includeDrafts: false,
    port: 3000,
  };
}

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    slug: 'test-post',
    title: 'Test Post',
    date: new Date('2024-01-01'),
    tags: ['test'],
    draft: false,
    content: 'Hello',
    html: '<p>Hello</p>',
    layout: 'default',
    ...overrides,
  };
}

describe('Renderer', () => {
  let renderer: Renderer;

  beforeEach(() => {
    renderer = new Renderer(TEMPLATE_DIR);
  });

  describe('layouts', () => {
    it('loads layouts from layouts directory', () => {
      renderer = new Renderer(TEMPLATE_DIR);
      const result = renderer.renderWithLayout(
        'post',
        'default',
        { page: { title: 'Hello' }, site: { title: 'Site', url: '' } },
      );
      expect(result).toContain('<html');
      expect(result).toContain('<h1>Hello</h1>');
    });

    it('renders body content inside layout', () => {
      const result = renderer.renderWithLayout(
        'post',
        'default',
        {
          page: { title: 'My Page', content: '<p>Body</p>' },
          site: { title: 'Site', url: '' },
        },
      );
      expect(result).toContain('<p>Body</p>');
      expect(result).toContain('My Page');
    });

    it('throws for missing layout', () => {
      expect(() =>
        renderer.renderWithLayout('post', 'nonexistent', {
          page: { title: 'X' },
          site: { title: 'S', url: '' },
        }),
      ).toThrow('Layout not found');
    });
  });

  describe('partials', () => {
    it('renders partials with {{> partialName}}', () => {
      const result = renderer.renderWithLayout(
        'post',
        'default',
        {
          page: { title: 'Test' },
          site: { title: 'Site', url: '' },
          tags: [{ name: 'js', count: 3 }],
        },
      );
      expect(result).toContain('<nav>');
      expect(result).toContain('Home');
    });
  });

  describe('renderPost', () => {
    it('renders a complete post page', () => {
      const post = makePost({
        title: 'My Article',
        html: '<p>Content here</p>',
        layout: 'post',
      });
      const result = renderer.renderPost(post, makeConfig());
      expect(result).toContain('<h1>My Article</h1>');
      expect(result).toContain('<p>Content here</p>');
      expect(result).toContain('<time>');
    });
  });

  describe('renderIndex', () => {
    it('renders index with list of posts', () => {
      const posts = [
        makePost({ title: 'Post A', slug: 'a' }),
        makePost({ title: 'Post B', slug: 'b' }),
      ];
      const result = renderer.renderIndex(posts, makeConfig());
      expect(result).toContain('Post A');
      expect(result).toContain('Post B');
      expect(result).toContain('/a/');
      expect(result).toContain('/b/');
    });

    it('includes tags in index context', () => {
      const posts = [
        makePost({ tags: ['js', 'css'] }),
        makePost({ tags: ['js'] }),
      ];
      const result = renderer.renderIndex(posts, makeConfig());
      expect(result).toContain('js');
    });
  });

  describe('renderTagPage', () => {
    it('renders a tag page with filtered posts', () => {
      const posts = [
        makePost({ title: 'Tagged Post', slug: 'tp', tags: ['featured'] }),
      ];
      const result = renderer.renderTagPage('featured', posts, makeConfig());
      expect(result).toContain('Tag: featured');
      expect(result).toContain('Tagged Post');
    });
  });

  describe('template loading', () => {
    it('throws when template file is not found', () => {
      expect(() => renderer.loadTemplate('nonexistent')).toThrow(
        'Template not found',
      );
    });

    it('caches loaded templates', () => {
      const t1 = renderer.loadTemplate('post');
      const t2 = renderer.loadTemplate('post');
      expect(t1).toBe(t2);
    });
  });
});
