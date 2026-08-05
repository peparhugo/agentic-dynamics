import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, toOutputPath, slugifyTag, collectTags, loadPages } from '../src/build.js';
import type { SiteConfig } from '../src/types.js';

async function makeFixtureSite(): Promise<SiteConfig> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'sprout-site-'));
  const sourceDir = path.join(root, 'content');
  const templateDir = path.join(root, 'templates');
  const outDir = path.join(root, 'out');

  await fs.mkdir(path.join(sourceDir, 'posts'), { recursive: true });
  await fs.mkdir(path.join(templateDir, 'layouts'), { recursive: true });
  await fs.mkdir(path.join(templateDir, 'partials'), { recursive: true });

  await fs.writeFile(
    path.join(sourceDir, 'index.md'),
    `---\ntitle: Home\n---\nWelcome home.`,
  );
  await fs.writeFile(
    path.join(sourceDir, 'posts', 'first.md'),
    `---\ntitle: First Post\ndate: 2024-01-10\ntags: [dev, notes]\n---\nHello **first**.\n\n\`\`\`js\nconst a = 1;\n\`\`\``,
  );
  await fs.writeFile(
    path.join(sourceDir, 'posts', 'second.md'),
    `---\ntitle: Second Post\ndate: 2024-02-20\ntags: [dev]\nlayout: post\n---\nSecond body.`,
  );
  await fs.writeFile(
    path.join(sourceDir, 'posts', 'secret.md'),
    `---\ntitle: Secret\ndate: 2024-03-01\ndraft: true\n---\nShh.`,
  );
  await fs.writeFile(path.join(sourceDir, 'style.css'), 'body{}');

  await fs.writeFile(
    path.join(templateDir, 'layouts', 'default.hbs'),
    `<html><head><title>{{title}} — {{site.title}}</title></head><body>{{> nav}}{{{content}}}</body></html>`,
  );
  await fs.writeFile(
    path.join(templateDir, 'layouts', 'post.hbs'),
    `<html><body class="post">{{{content}}}</body></html>`,
  );
  await fs.writeFile(path.join(templateDir, 'partials', 'nav.hbs'), `<nav>{{site.title}}</nav>`);
  await fs.writeFile(
    path.join(templateDir, 'tag.hbs'),
    `<h1>#{{tag}}</h1><ul>{{#each pages}}<li>{{frontmatter.title}}</li>{{/each}}</ul>`,
  );

  return {
    sourceDir,
    templateDir,
    outDir,
    baseUrl: 'https://site.test',
    title: 'Fixture Site',
    description: 'A test site',
    includeDrafts: false,
  };
}

describe('toOutputPath', () => {
  it('maps posts to pretty URLs', () => {
    expect(toOutputPath('posts/hello.md')).toEqual({
      outputPath: 'posts/hello/index.html',
      url: '/posts/hello/',
    });
  });
  it('keeps index files in place', () => {
    expect(toOutputPath('index.md')).toEqual({ outputPath: 'index.html', url: '/' });
    expect(toOutputPath('docs/index.md')).toEqual({
      outputPath: 'docs/index.html',
      url: '/docs/',
    });
  });
});

describe('slugifyTag', () => {
  it('slugifies', () => {
    expect(slugifyTag('Hello World!')).toBe('hello-world');
    expect(slugifyTag('C++ / Rust')).toBe('c-rust');
  });
});

describe('buildSite', () => {
  let config: SiteConfig;
  beforeEach(async () => {
    config = await makeFixtureSite();
  });
  afterEach(async () => {
    await fs.rm(path.dirname(config.sourceDir), { recursive: true, force: true });
  });

  it('builds pages with layouts and partials', async () => {
    const result = await buildSite(config);
    expect(result.pages).toHaveLength(3); // draft excluded

    const home = await fs.readFile(path.join(config.outDir, 'index.html'), 'utf8');
    expect(home).toContain('<title>Home — Fixture Site</title>');
    expect(home).toContain('<nav>Fixture Site</nav>');
    expect(home).toContain('Welcome home.');

    const first = await fs.readFile(
      path.join(config.outDir, 'posts/first/index.html'),
      'utf8',
    );
    expect(first).toContain('<strong>first</strong>');
    expect(first).toContain('hljs'); // syntax highlighting present
  });

  it('respects per-page layout from frontmatter', async () => {
    await buildSite(config);
    const second = await fs.readFile(
      path.join(config.outDir, 'posts/second/index.html'),
      'utf8',
    );
    expect(second).toContain('class="post"');
    expect(second).not.toContain('<nav>');
  });

  it('excludes drafts by default, includes with includeDrafts', async () => {
    await buildSite(config);
    await expect(
      fs.stat(path.join(config.outDir, 'posts/secret/index.html')),
    ).rejects.toThrow();

    const result = await buildSite({ ...config, includeDrafts: true });
    expect(result.pages.map((p) => p.frontmatter.title)).toContain('Secret');
    const secret = await fs.readFile(
      path.join(config.outDir, 'posts/secret/index.html'),
      'utf8',
    );
    expect(secret).toContain('Shh.');
  });

  it('generates tag index pages using the tag template', async () => {
    const result = await buildSite(config);
    expect(result.tagPages.sort()).toEqual(['tags/dev/index.html', 'tags/notes/index.html']);
    const dev = await fs.readFile(path.join(config.outDir, 'tags/dev/index.html'), 'utf8');
    expect(dev).toContain('#dev');
    expect(dev).toContain('First Post');
    expect(dev).toContain('Second Post');
    const notes = await fs.readFile(
      path.join(config.outDir, 'tags/notes/index.html'),
      'utf8',
    );
    expect(notes).not.toContain('Second Post');
  });

  it('generates a valid RSS feed sorted newest-first', async () => {
    await buildSite(config);
    const rss = await fs.readFile(path.join(config.outDir, 'feed.xml'), 'utf8');
    expect(rss).toContain('<?xml version="1.0" encoding="UTF-8"?>');
    expect(rss).toContain('<rss version="2.0">');
    expect(rss).toContain('<title>Fixture Site</title>');
    expect(rss).toContain('<link>https://site.test/posts/first/</link>');
    expect(rss.indexOf('Second Post')).toBeLessThan(rss.indexOf('First Post'));
    expect(rss).not.toContain('Secret');
    expect(rss).toContain('<category>dev</category>');
  });

  it('copies static assets through', async () => {
    await buildSite(config);
    expect(await fs.readFile(path.join(config.outDir, 'style.css'), 'utf8')).toBe('body{}');
  });

  it('sorts pages newest-first with undated pages last', async () => {
    const pages = await loadPages(config);
    expect(pages.map((p) => p.frontmatter.title)).toEqual([
      'Second Post',
      'First Post',
      'Home',
    ]);
  });

  it('collectTags groups pages by tag', async () => {
    const pages = await loadPages(config);
    const tags = collectTags(pages);
    expect([...tags.keys()].sort()).toEqual(['dev', 'notes']);
    expect(tags.get('dev')).toHaveLength(2);
  });
});
