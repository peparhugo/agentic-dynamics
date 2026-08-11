import fs from 'fs';
import path from 'path';
import { SsgEngine, BuildStats, CacheManager } from './ssg-engine';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { Plugin, BuildContext } from './plugin';
import { PageData } from './types';

const tmpDir = path.join(__dirname, '..', '.test-tmp-inc');

function setupContentDir(files: Record<string, string>): string {
  const contentDir = path.join(tmpDir, 'content');
  if (fs.existsSync(contentDir)) {
    fs.rmSync(contentDir, { recursive: true });
  }
  fs.mkdirSync(contentDir, { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    fs.writeFileSync(path.join(contentDir, name), body);
  }
  return contentDir;
}

function freshOutputDir(): string {
  const dir = path.join(tmpDir, 'dist');
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true });
  }
  return dir;
}

function distPath(): string {
  return path.join(tmpDir, 'dist');
}

function setupTemplatesDir(files: Record<string, string>): string {
  const templatesDir = path.join(tmpDir, 'templates');
  if (fs.existsSync(templatesDir)) {
    fs.rmSync(templatesDir, { recursive: true });
  }
  fs.mkdirSync(templatesDir, { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    const fullPath = path.join(templatesDir, name);
    const dir = path.dirname(fullPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(fullPath, body);
  }
  return templatesDir;
}

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true });
  }
});

describe('incremental builds', () => {
  it('creates .ssg-cache.json after incremental build', async () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: Hello
date: 2024-01-01
---
# Hello`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    const cachePath = path.join(dist, '.ssg-cache.json');
    expect(fs.existsSync(cachePath)).toBe(true);

    const cacheData = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
    expect(cacheData.version).toBe(1);
    expect(cacheData.entries).toHaveProperty('post');
    expect(cacheData.entries.post.contentHash).toBeTruthy();
    expect(cacheData.entries.post.templateHash).toBeTruthy();
    expect(cacheData.entries.post.html).toContain('<!DOCTYPE html>');
    expect(cacheData.entries.post.html).toContain('Hello');
    expect(cacheData.entries.post.frontmatter.title).toBe('Hello');
  });

  it('skip unchanged pages on second incremental build', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    const stats1 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats1.pagesBuilt).toBe(2);
    expect(stats1.pagesSkipped).toBe(0);

    const stats2 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats2.pagesBuilt).toBe(0);
    expect(stats2.pagesSkipped).toBe(2);

    expect(fs.existsSync(path.join(dist, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(dist, 'b.html'))).toBe(true);
    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('Post A');
  });

  it('rebuilds only changed pages on incremental build', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    fs.writeFileSync(path.join(contentDir, 'a.md'), `---
title: Post A Updated
date: 2024-01-01
---
# A Updated`);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(1);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('Post A Updated');
  });

  it('rebuilds all pages when template file changes', async () => {
    const templatesDir = setupTemplatesDir({
      'default.hbs': `<main>{{{content}}}</main>`,
      'layouts/default.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>`,
    });

    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir, incremental: true });

    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), `<main class="updated">{{{content}}}</main>`);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir, incremental: true });
    expect(stats.pagesBuilt).toBe(2);
    expect(stats.pagesSkipped).toBe(0);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('class="updated"');
  });

  it('rebuilds all pages when layout template changes', async () => {
    const templatesDir = setupTemplatesDir({
      'default.hbs': `<main>{{{content}}}</main>`,
      'layouts/default.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>`,
    });

    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir, incremental: true });

    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'),
      `<!DOCTYPE html><html><head><title>{{title}}</title></head><body class="new-layout">{{{body}}}</body></html>`);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir, incremental: true });
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(0);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('class="new-layout"');
  });

  it('rebuilds all pages when partial template changes', async () => {
    const templatesDir = setupTemplatesDir({
      'default.hbs': `<main>{{> header}}{{{content}}}</main>`,
      'layouts/default.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>`,
      'partials/header.hbs': `<header>Original Header</header>`,
    });

    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir, incremental: true });

    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), `<header>Updated Header</header>`);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir, incremental: true });
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(0);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('Updated Header');
    expect(aHtml).not.toContain('Original Header');
  });

  it('clean flag forces full rebuild and recreates cache for subsequent builds', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    const stats1 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats1.pagesBuilt).toBe(1);

    const stats2 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true, clean: true });
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(0);

    const stats3 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats3.pagesBuilt).toBe(0);
    expect(stats3.pagesSkipped).toBe(1);

    expect(fs.existsSync(path.join(dist, 'a.html'))).toBe(true);
  });

  it('does full build when no cache exists with --incremental', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(0);

    expect(fs.existsSync(path.join(dist, 'a.html'))).toBe(true);
  });

  it('non-incremental builds do not create cache', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist });
    expect(fs.existsSync(path.join(dist, '.ssg-cache.json'))).toBe(false);
  });

  it('non-incremental builds still work correctly (existing functionality)', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist });
    expect(fs.existsSync(path.join(dist, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(dist, 'index.html'))).toBe(true);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('Post A');
  });

  it('new pages added are picked up on incremental build', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    fs.writeFileSync(path.join(contentDir, 'b.md'), `---
title: Post B
date: 2024-02-01
---
# B`);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(1);

    expect(fs.existsSync(path.join(dist, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(dist, 'b.html'))).toBe(true);
    const bHtml = fs.readFileSync(path.join(dist, 'b.html'), 'utf-8');
    expect(bHtml).toContain('Post B');
  });

  it('build stats reports correct numbers', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    const stats1 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats1.pagesBuilt).toBe(2);
    expect(stats1.pagesSkipped).toBe(0);
    expect(stats1.timeSavedMs).toBe(0);

    const stats2 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats2.pagesBuilt).toBe(0);
    expect(stats2.pagesSkipped).toBe(2);
    expect(stats2.timeSavedMs).toBeGreaterThan(0);
  });

  it('recreates cache if manifest file is corrupted', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    const stats1 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats1.pagesBuilt).toBe(1);

    fs.writeFileSync(path.join(dist, '.ssg-cache.json'), 'not valid json {{{');

    const stats2 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(0);

    expect(fs.existsSync(path.join(dist, 'a.html'))).toBe(true);
  });

  it('uses cached HTML without re-rendering for skipped pages', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const renderCounts: string[] = [];

    const trackingPlugin: Plugin = {
      name: 'tracking',
      onFile(page: PageData, _ctx: BuildContext): PageData {
        renderCounts.push('onFile:' + page.slug);
        return page;
      },
    };

    const engine = new SsgEngine([
      new MarkdownPlugin(),
      trackingPlugin,
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(renderCounts.filter(c => c === 'onFile:a')).toHaveLength(1);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats.pagesSkipped).toBe(1);
    expect(renderCounts.filter(c => c === 'onFile:a')).toHaveLength(1);
  });

  it('cached HTML matches rendered HTML content', async () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: Cached Post
date: 2024-06-15
tags:
  - blog
---
# Cached Post

This content should be in the cached output.`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    const cachePath = path.join(dist, '.ssg-cache.json');
    const cacheData = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));

    const cachedHtml = cacheData.entries.post.html;
    const diskHtml = fs.readFileSync(path.join(dist, 'post.html'), 'utf-8');

    expect(cachedHtml).toContain('Cached Post');
    expect(cachedHtml).toContain('This content should be in the cached output.');
    expect(cachedHtml).toContain('<!DOCTYPE html>');

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    const diskHtmlAfterSkip = fs.readFileSync(path.join(dist, 'post.html'), 'utf-8');
    expect(diskHtmlAfterSkip).toContain('Cached Post');
    expect(diskHtmlAfterSkip).toContain('This content should be in the cached output.');
    expect(diskHtmlAfterSkip).toContain('<!DOCTYPE html>');
  });

  it('handles multiple incremental builds with alternating changes', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A v1`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B v1`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    fs.writeFileSync(path.join(contentDir, 'a.md'), `---
title: Post A
date: 2024-01-01
---
# A v2`);

    const stats1 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats1.pagesBuilt).toBe(1);
    expect(stats1.pagesSkipped).toBe(1);

    fs.writeFileSync(path.join(contentDir, 'b.md'), `---
title: Post B
date: 2024-02-01
---
# B v2`);

    const stats2 = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(1);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    const bHtml = fs.readFileSync(path.join(dist, 'b.html'), 'utf-8');
    expect(aHtml).toContain('A v2');
    expect(bHtml).toContain('B v2');
  });

  it('frontmatter changes trigger rebuild', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Old Title
date: 2024-01-01
---
# Content`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    fs.writeFileSync(path.join(contentDir, 'a.md'), `---
title: New Title
date: 2024-01-01
---
# Content`);

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(0);

    const aHtml = fs.readFileSync(path.join(dist, 'a.html'), 'utf-8');
    expect(aHtml).toContain('New Title');
  });

  it('cache persists frontmatter for skipped pages correctly', async () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: Special Post
date: 2024-07-01
tags:
  - cached
  - test
template: default
layout: default
---
# Special Content`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    const cachePath = path.join(dist, '.ssg-cache.json');
    const cacheData = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
    const entry = cacheData.entries.post;

    expect(entry.frontmatter.title).toBe('Special Post');
    expect(entry.frontmatter.date).toBe('2024-07-01');
    expect(entry.frontmatter.tags).toEqual(['cached', 'test']);
    expect(entry.frontmatter.template).toBe('default');
    expect(entry.frontmatter.layout).toBe('default');
  });

  it('index.html is always regenerated even when pages are skipped', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    const firstIndexTime = fs.statSync(path.join(dist, 'index.html')).mtimeMs;

    await new Promise(r => setTimeout(r, 100));

    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    expect(stats.pagesSkipped).toBe(1);

    const secondIndexTime = fs.statSync(path.join(dist, 'index.html')).mtimeMs;
    expect(secondIndexTime).toBeGreaterThan(firstIndexTime);
  });

  it('CacheManager computes consistent hashes for unchanged files', () => {
    const contentDir = setupContentDir({
      'test.md': `---
title: Test
date: 2024-01-01
---
# Test`,
    });

    const hash1 = CacheManager.computeContentHash(path.join(contentDir, 'test.md'));
    const hash2 = CacheManager.computeContentHash(path.join(contentDir, 'test.md'));

    expect(hash1).toBe(hash2);
    expect(hash1.length).toBe(64);
  });

  it('CacheManager computes different hashes for different files', () => {
    const contentDir = setupContentDir({
      'a.md': 'Content A',
      'b.md': 'Content B',
    });

    const hashA = CacheManager.computeContentHash(path.join(contentDir, 'a.md'));
    const hashB = CacheManager.computeContentHash(path.join(contentDir, 'b.md'));

    expect(hashA).not.toBe(hashB);
  });

  it('CacheManager load/save/delete cycle works', () => {
    const dist = freshOutputDir();
    const cm = new CacheManager(dist);

    expect(cm.load()).toBe(false);

    cm.setEntry({
      slug: 'test',
      contentHash: 'abc123',
      templateHash: 'def456',
      html: '<html></html>',
      frontmatter: { title: 'Test', date: '', tags: [] },
    });
    cm.save();

    const cm2 = new CacheManager(dist);
    expect(cm2.load()).toBe(true);
    const entry = cm2.getEntry('test');
    expect(entry).toBeTruthy();
    expect(entry!.contentHash).toBe('abc123');

    cm2.delete();
    const cm3 = new CacheManager(dist);
    expect(cm3.load()).toBe(false);
  });

  it('CacheManager isStale detects content changes', () => {
    const dist = freshOutputDir();
    const cm = new CacheManager(dist);

    cm.setEntry({
      slug: 'test',
      contentHash: 'hash-v1',
      templateHash: 'tpl-v1',
      html: '<html></html>',
      frontmatter: { title: 'Test', date: '', tags: [] },
    });

    expect(cm.isStale('test', 'hash-v1', 'tpl-v1')).toBe(false);
    expect(cm.isStale('test', 'hash-v2', 'tpl-v1')).toBe(true);
    expect(cm.isStale('test', 'hash-v1', 'tpl-v2')).toBe(true);
    expect(cm.isStale('nonexistent', 'hash-v1', 'tpl-v1')).toBe(true);
  });

  it('CacheManager getCachedHtmlMap returns correct map', () => {
    const dist = freshOutputDir();
    const cm = new CacheManager(dist);

    cm.setEntry({
      slug: 'a',
      contentHash: 'hash-a',
      templateHash: 'tpl',
      html: '<html>A</html>',
      frontmatter: { title: 'A', date: '', tags: [] },
    });
    cm.setEntry({
      slug: 'b',
      contentHash: 'hash-b',
      templateHash: 'tpl',
      html: '<html>B</html>',
      frontmatter: { title: 'B', date: '', tags: [] },
    });

    const map = cm.getCachedHtmlMap();
    expect(map.size).toBe(2);
    expect(map.get('a')).toBe('<html>A</html>');
    expect(map.get('b')).toBe('<html>B</html>');
  });

  it('build with incremental flag reports stats when pages are skipped', async () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
    });
    const dist = freshOutputDir();
    const engine = new SsgEngine([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });
    const stats = await engine.build({ contentDir, outputDir: dist, templatesDir: dist, incremental: true });

    expect(stats.pagesBuilt).toBe(0);
    expect(stats.pagesSkipped).toBe(1);
    expect(stats.timeSavedMs).toBeGreaterThan(0);
  });
});

describe('parseArgs with new flags', () => {
  const { parseArgs } = require('./index');

  it('parses --incremental flag', () => {
    const result = parseArgs(['build', '--incremental']);
    expect(result.incremental).toBe(true);
    expect(result.clean).toBe(false);
  });

  it('parses --clean flag', () => {
    const result = parseArgs(['build', '--clean']);
    expect(result.clean).toBe(true);
    expect(result.incremental).toBe(false);
  });

  it('parses both --incremental and --clean together', () => {
    const result = parseArgs(['build', '--incremental', '--clean']);
    expect(result.incremental).toBe(true);
    expect(result.clean).toBe(true);
  });

  it('defaults to false for incremental and clean', () => {
    const result = parseArgs(['build']);
    expect(result.incremental).toBe(false);
    expect(result.clean).toBe(false);
  });

  it('parses incremental with other flags', () => {
    const result = parseArgs(['build', '--content', './mycontent', '--output', './out', '--incremental']);
    expect(result.contentDir).toBe('./mycontent');
    expect(result.outputDir).toBe('./out');
    expect(result.incremental).toBe(true);
  });
});
