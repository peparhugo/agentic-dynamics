import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown, renderPage } from '../src';
import { parseArguments } from '../src/cli';

describe('parseMarkdown', () => {
  it('parses YAML frontmatter and Markdown', () => {
    const result = parseMarkdown(`---
title: "A post"
date: 2026-08-16
tags:
  - TypeScript
  - static sites
---
# Hello

This is **bold**.`);

    expect(result.data).toEqual(expect.objectContaining({
      title: 'A post',
      date: '2026-08-16',
      tags: ['TypeScript', 'static sites'],
    }));
    expect(result.html).toContain('<h1>Hello</h1>');
    expect(result.html).toContain('<strong>bold</strong>');
    expect(result.content).not.toContain('title:');
  });

  it('supports inline tags and documents without frontmatter', () => {
    expect(parseMarkdown('---\ntags: [one, two]\n---\nText').data.tags).toEqual(['one', 'two']);
    expect(parseMarkdown('Plain *text*').html).toContain('<em>text</em>');
  });
});

describe('renderPage', () => {
  it('escapes frontmatter while retaining generated Markdown HTML', () => {
    const html = renderPage({
      title: '<unsafe>',
      data: { tags: ['a&b'] },
      html: '<p>Safe Markdown</p>',
    });
    expect(html).toContain('&lt;unsafe&gt;');
    expect(html).toContain('a&amp;b');
    expect(html).toContain('<p>Safe Markdown</p>');
  });
});

describe('buildSite', () => {
  let temporaryDirectory: string;

  beforeEach(async () => {
    temporaryDirectory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
  });

  afterEach(async () => {
    await fs.rm(temporaryDirectory, { recursive: true, force: true });
  });

  it('builds pages recursively and creates a linked index', async () => {
    const contentDir = path.join(temporaryDirectory, 'posts');
    const outputDir = path.join(temporaryDirectory, 'site');
    await fs.mkdir(path.join(contentDir, 'guides'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'new.md'), '---\ntitle: New post\ndate: 2026-08-16\n---\nNewest');
    await fs.writeFile(path.join(contentDir, 'guides', 'start.md'), '---\ntitle: Start here\n---\nGuide');
    await fs.writeFile(path.join(contentDir, 'ignored.txt'), 'Not a page');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(2);
    await expect(fs.readFile(path.join(outputDir, 'new.html'), 'utf8')).resolves.toContain('Newest');
    await expect(fs.readFile(path.join(outputDir, 'guides', 'start.html'), 'utf8')).resolves.toContain('Guide');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('href="new.html"');
    expect(index).toContain('href="guides/start.html"');
    expect(index.indexOf('New post')).toBeLessThan(index.indexOf('Start here'));
  });

  it('renders default templates, layouts, and partials', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'site');
    const templatesDir = path.join(temporaryDirectory, 'templates');
    await fs.mkdir(contentDir, { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'partials', 'shared'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'hello.md'), '---\ntitle: A & B\nshowNav: true\n---\n**Welcome**');
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '{{> shared/nav}}<article><h1>{{title}}</h1>{{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<!doctype html><body>{{{body}}}{{> footer}}</body>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'shared', 'nav.hbs'), '{{#if showNav}}<nav>{{title}}</nav>{{/if}}');
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(html).toContain('<nav>A &amp; B</nav>');
    expect(html).toContain('<h1>A &amp; B</h1><p><strong>Welcome</strong></p>');
    expect(html).toContain('<footer>Footer</footer>');
  });

  it('supports per-page templates and layouts', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'site');
    const templatesDir = path.join(temporaryDirectory, 'templates');
    await fs.mkdir(contentDir, { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'post.md'), '---\ntitle: Post\ntemplate: post\nlayout: article\ntags: [one, two]\n---\nBody');
    await fs.writeFile(path.join(templatesDir, 'post.hbs'), '<section>{{#each tags}}<b>{{this}}</b>{{/each}}{{{html}}}</section>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'article.hbs'), '<main data-title="{{title}}">{{{body}}}</main>');

    await buildSite({ contentDir, outputDir, templatesDir });

    await expect(fs.readFile(path.join(outputDir, 'post.html'), 'utf8')).resolves.toBe(
      '<main data-title="Post"><section><b>one</b><b>two</b><p>Body</p>\n</section></main>',
    );
  });

  it('reports an explicitly requested template that does not exist', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'site');
    const templatesDir = path.join(temporaryDirectory, 'templates');
    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(path.join(contentDir, 'post.md'), '---\ntemplate: missing\n---\nBody');

    await expect(buildSite({ contentDir, outputDir, templatesDir })).rejects.toThrow('Template not found: missing');
  });
});

describe('parseArguments', () => {
  it('accepts build paths', () => {
    expect(parseArguments(['build', '--content', 'articles', '--output', 'public', '--templates', 'views'])).toEqual({
      contentDir: 'articles',
      outputDir: 'public',
      templatesDir: 'views',
    });
  });

  it('rejects invalid commands and incomplete options', () => {
    expect(() => parseArguments(['serve'])).toThrow('Usage:');
    expect(() => parseArguments(['build', '--content'])).toThrow('incomplete');
  });
});
