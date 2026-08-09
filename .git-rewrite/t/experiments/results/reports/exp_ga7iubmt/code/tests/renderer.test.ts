import { describe, it, expect, beforeAll } from 'vitest';
import { loadTemplates, renderPage, registerHelpers } from '../src/renderer.js';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = join(__dirname, 'fixtures', 'templates');

const site = {
  title: 'Test Site',
  description: 'A test blog',
  url: 'https://example.com',
};

beforeAll(() => {
  registerHelpers(site);
});

describe('loadTemplates', () => {
  it('loads all templates from directory', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    expect(templates.has('post')).toBe(true);
    expect(templates.has('tag')).toBe(true);
    expect(templates.has('index')).toBe(true);
    expect(templates.has('rss')).toBe(true);
    expect(layout).not.toBeNull();
  });

  it('registers partials', async () => {
    await loadTemplates(TEMPLATES_DIR);

    // render a layout that uses a partial
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);
    const html = renderPage(templates, layout, 'index', {
      site,
      posts: [],
      title: 'Test',
    });

    expect(html).toContain('<nav>');
    expect(html).toContain('Home');
  });
});

describe('renderPage', () => {
  it('renders a post template', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'post', {
      site,
      title: 'Hello World',
      date: '2024-01-15',
      tags: ['javascript', 'tutorial'],
      content: '<p>Hello content</p>',
      url: '/hello-world/',
    });

    expect(html).toContain('Hello World');
    expect(html).toContain('<p>Hello content</p>');
    expect(html).toContain('href="/tags/javascript/"');
    expect(html).toContain('href="/tags/tutorial/"');
  });

  it('renders a tag index page', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'tag', {
      site,
      tag: 'javascript',
      title: 'Tag: javascript',
      posts: [
        {
          title: 'Post 1',
          url: '/post-1/',
        },
        {
          title: 'Post 2',
          url: '/post-2/',
        },
      ] as any,
    });

    expect(html).toContain('Tag: javascript');
    expect(html).toContain('Post 1');
    expect(html).toContain('Post 2');
  });

  it('renders the index page', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'index', {
      site,
      title: site.title,
      posts: [
        {
          title: 'Blog Post',
          url: '/blog-post/',
          date: '2024-03-01',
        },
      ] as any,
    });

    expect(html).toContain('Test Site');
    expect(html).toContain('Blog Post');
  });

  it('wraps content in layout', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'post', {
      site,
      title: 'Wrapped',
      content: '<p>Inner</p>',
    });

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<meta charset="UTF-8">');
    expect(html).toContain('<article>');
    expect(html).toContain('<main>');
    expect(html).toContain('Wrapped');
  });

  it('does not wrap RSS template in layout', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'rss', {
      site,
      title: site.title,
      posts: [],
    });

    expect(html).toContain('<?xml');
    expect(html).toContain('<rss version="2.0"');
    expect(html).not.toContain('<!DOCTYPE html>');
  });

  it('throws for missing template', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    expect(() =>
      renderPage(templates, layout, 'nonexistent', { site, title: 'X' }),
    ).toThrow('Template "nonexistent" not found');
  });
});

describe('helpers', () => {
  it('formats dates with dateFormat', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'post', {
      site,
      title: 'Dated',
      date: '2024-01-15',
      content: '<p>Test</p>',
    });

    expect(html).toContain('January 15, 2024');
  });

  it('generates tag URLs', async () => {
    const { templates, layout } = await loadTemplates(TEMPLATES_DIR);

    const html = renderPage(templates, layout, 'post', {
      site,
      title: 'Tagged',
      tags: ['TypeScript'],
      content: '<p>Test</p>',
    });

    expect(html).toContain('/tags/typescript/');
  });
});
