import fs from 'fs';
import path from 'path';
import os from 'os';
import { Page } from '../types';
import { generateSiteIncremental } from '../incremental';
import { CacheManager } from '../cache';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'test-page',
    frontmatter: {
      title: 'Test Page',
      date: '2024-06-15',
      tags: ['typescript', 'testing'],
    },
    content: 'Some markdown content',
    html: '<p>Some markdown content</p>',
    ...overrides,
  };
}

function writeMarkdownFile(dir: string, slug: string, title: string, body: string): void {
  const content = `---
title: ${title}
date: '2024-01-01'
tags: []
---
${body}`;
  fs.writeFileSync(path.join(dir, `${slug}.md`), content, 'utf-8');
}

describe('generateSiteIncremental', () => {
  let tmpDir: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incr-test-'));
    contentDir = path.join(tmpDir, 'content');
    outputDir = path.join(tmpDir, 'output');
    templatesDir = path.join(tmpDir, 'templates');
    fs.mkdirSync(contentDir);
    fs.mkdirSync(outputDir);
    fs.mkdirSync(templatesDir);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  describe('basic incremental builds', () => {
    it('generates all pages on a clean build', () => {
      writeMarkdownFile(contentDir, 'alpha', 'Alpha', 'Alpha content');
      writeMarkdownFile(contentDir, 'beta', 'Beta', 'Beta content');

      const pages = [
        { slug: 'alpha', frontmatter: { title: 'Alpha', date: '2024-01-01', tags: [] }, content: 'Alpha content', html: '<p>Alpha content</p>' },
        { slug: 'beta', frontmatter: { title: 'Beta', date: '2024-01-01', tags: [] }, content: 'Beta content', html: '<p>Beta content</p>' },
      ];

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);

      expect(stats.pagesBuilt).toBe(3); // alpha, beta, index
      expect(stats.pagesSkipped).toBe(0);
      expect(fs.existsSync(path.join(outputDir, 'alpha.html'))).toBe(true);
      expect(fs.existsSync(path.join(outputDir, 'beta.html'))).toBe(true);
      expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    });

    it('creates cache file after build', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);

      expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(true);
    });

    it('skips unchanged pages on second build', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');
      writeMarkdownFile(contentDir, 'page2', 'Page 2', 'Content 2');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
        { slug: 'page2', frontmatter: { title: 'Page 2', date: '2024-01-01', tags: [] }, content: 'Content 2', html: '<p>Content 2</p>' },
      ];

      const stats1 = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats1.pagesBuilt).toBe(3); // page1, page2, index
      expect(stats1.pagesSkipped).toBe(0);

      const stats2 = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats2.pagesBuilt).toBe(0); // nothing changed
      expect(stats2.pagesSkipped).toBe(3); // page1, page2, index all skipped
    });

    it('rebuilds only changed page', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');
      writeMarkdownFile(contentDir, 'page2', 'Page 2', 'Content 2');

      const pages1 = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
        { slug: 'page2', frontmatter: { title: 'Page 2', date: '2024-01-01', tags: [] }, content: 'Content 2', html: '<p>Content 2</p>' },
      ];

      generateSiteIncremental(pages1, outputDir, contentDir, templatesDir);

      writeMarkdownFile(contentDir, 'page2', 'Page 2 Changed', 'Content 2 changed');

      const pages2 = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
        { slug: 'page2', frontmatter: { title: 'Page 2 Changed', date: '2024-01-01', tags: [] }, content: 'Content 2 changed', html: '<p>Content 2 changed</p>' },
      ];

      const stats = generateSiteIncremental(pages2, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(2); // page2 rebuilt + index rebuilt
      expect(stats.pagesSkipped).toBe(1); // page1 skipped
    });

    it('rebuilds all when clean flag is passed', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir, true);
      expect(stats.pagesBuilt).toBe(2); // page1 + index rebuilt
      expect(stats.pagesSkipped).toBe(0);
    });

    it('handles new pages added after initial build', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages1 = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages1, outputDir, contentDir, templatesDir);

      writeMarkdownFile(contentDir, 'page2', 'Page 2', 'Content 2');

      const pages2 = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
        { slug: 'page2', frontmatter: { title: 'Page 2', date: '2024-01-01', tags: [] }, content: 'Content 2', html: '<p>Content 2</p>' },
      ];

      const stats = generateSiteIncremental(pages2, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(2); // page2 + index
      expect(stats.pagesSkipped).toBe(1); // page1 skipped
      expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);
    });

    it('prunes cache entries for deleted pages', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');
      writeMarkdownFile(contentDir, 'page2', 'Page 2', 'Content 2');

      const pages1 = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
        { slug: 'page2', frontmatter: { title: 'Page 2', date: '2024-01-01', tags: [] }, content: 'Content 2', html: '<p>Content 2</p>' },
      ];

      generateSiteIncremental(pages1, outputDir, contentDir, templatesDir);

      fs.unlinkSync(path.join(contentDir, 'page2.md'));

      const pages2 = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      const stats = generateSiteIncremental(pages2, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(1); // index rebuilt (page1 unchanged, page2 removed)
      expect(stats.pagesSkipped).toBe(1); // page1 skipped

      const cache = new CacheManager(outputDir);
      cache.load();
      const manifest = (cache as any).manifest;
      expect(manifest.pages['page2']).toBeUndefined();
      expect(manifest.pages['page1']).toBeDefined();
    });
  });

  describe('template change detection', () => {
    it('rebuilds pages when template files change', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);

      fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<h1 class="custom">{{title}}</h1>\n{{{content}}}');

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(2); // page1 + index rebuilt
      expect(stats.pagesSkipped).toBe(0);
    });

    it('rebuilds pages when layout template changes', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
      fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);

      fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<html><head><title>Changed: {{title}}</title></head><body>{{{body}}}</body></html>');

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(2); // page1 + index rebuilt
      expect(stats.pagesSkipped).toBe(0);
    });

    it('treats missing templates dir as builtin defaults', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      const noTemplatesDir = path.join(tmpDir, 'no-templates');
      const stats1 = generateSiteIncremental(pages, outputDir, contentDir, noTemplatesDir);
      expect(stats1.pagesBuilt).toBe(2);

      const stats2 = generateSiteIncremental(pages, outputDir, contentDir, noTemplatesDir);
      expect(stats2.pagesSkipped).toBe(2); // all skipped
    });
  });

  describe('stats reporting', () => {
    it('reports correct stats for full build', () => {
      writeMarkdownFile(contentDir, 'a', 'A', 'A content');
      writeMarkdownFile(contentDir, 'b', 'B', 'B content');
      writeMarkdownFile(contentDir, 'c', 'C', 'C content');

      const pages = [
        { slug: 'a', frontmatter: { title: 'A', date: '2024-01-01', tags: [] }, content: 'A content', html: '<p>A content</p>' },
        { slug: 'b', frontmatter: { title: 'B', date: '2024-01-01', tags: [] }, content: 'B content', html: '<p>B content</p>' },
        { slug: 'c', frontmatter: { title: 'C', date: '2024-01-01', tags: [] }, content: 'C content', html: '<p>C content</p>' },
      ];

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(4); // 3 pages + index
      expect(stats.pagesSkipped).toBe(0);
      expect(stats.totalPages).toBe(4);
    });

    it('reports correct stats for incremental build with no changes', () => {
      writeMarkdownFile(contentDir, 'a', 'A', 'A content');

      const pages = [
        { slug: 'a', frontmatter: { title: 'A', date: '2024-01-01', tags: [] }, content: 'A content', html: '<p>A content</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(0);
      expect(stats.pagesSkipped).toBe(2); // page + index
      expect(stats.totalPages).toBe(2);
    });

    it('reports correct stats when page source changes', () => {
      writeMarkdownFile(contentDir, 'a', 'A', 'A content');

      const pages1 = [
        { slug: 'a', frontmatter: { title: 'A', date: '2024-01-01', tags: [] }, content: 'A content', html: '<p>A content</p>' },
      ];

      generateSiteIncremental(pages1, outputDir, contentDir, templatesDir);

      writeMarkdownFile(contentDir, 'a', 'A Updated', 'A content updated');

      const pages2 = [
        { slug: 'a', frontmatter: { title: 'A Updated', date: '2024-01-01', tags: [] }, content: 'A content updated', html: '<p>A content updated</p>' },
      ];

      const stats = generateSiteIncremental(pages2, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(2); // page + index
      expect(stats.pagesSkipped).toBe(0);
    });
  });

  describe('cache persistence', () => {
    it('cache survives between builds', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);

      expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(true);

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(0);
      expect(stats.pagesSkipped).toBe(2);
    });

    it('treats missing cache as clean build', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      const cachePath = path.join(outputDir, '.ssg-cache.json');
      expect(fs.existsSync(cachePath)).toBe(false);

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(2); // full build
      expect(stats.pagesSkipped).toBe(0);
    });

    it('clear flag deletes existing cache', () => {
      writeMarkdownFile(contentDir, 'page1', 'Page 1', 'Content 1');

      const pages = [
        { slug: 'page1', frontmatter: { title: 'Page 1', date: '2024-01-01', tags: [] }, content: 'Content 1', html: '<p>Content 1</p>' },
      ];

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(true);

      generateSiteIncremental(pages, outputDir, contentDir, templatesDir, true);
      expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(true); // rebuilt

      const stats = generateSiteIncremental(pages, outputDir, contentDir, templatesDir);
      expect(stats.pagesBuilt).toBe(0); // pages still match after clean rebuild
    });
  });
});

describe('CacheManager', () => {
  let tmpDir: string;
  let outputDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cache-test-'));
    outputDir = path.join(tmpDir, 'output');
    fs.mkdirSync(outputDir);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('saves and loads manifest', () => {
    const cm = new CacheManager(outputDir);
    cm.update('page1', 'hash1', 'tpl1');
    cm.save();

    const cm2 = new CacheManager(outputDir);
    cm2.load();
    expect(cm2.isStale('page1', 'hash1', 'tpl1')).toBe(false);
    expect(cm2.isStale('page1', 'hash2', 'tpl1')).toBe(true);
  });

  it('considers missing entry as stale', () => {
    const cm = new CacheManager(outputDir);
    cm.load();
    expect(cm.isStale('nonexistent', 'hash1', 'tpl1')).toBe(true);
  });

  it('considers changed source hash as stale', () => {
    const cm = new CacheManager(outputDir);
    cm.update('page1', 'hash1', 'tpl1');
    expect(cm.isStale('page1', 'hash2', 'tpl1')).toBe(true);
  });

  it('considers changed template hash as stale', () => {
    const cm = new CacheManager(outputDir);
    cm.update('page1', 'hash1', 'tpl1');
    expect(cm.isStale('page1', 'hash1', 'tpl2')).toBe(true);
  });

  it('considers unchanged entry as fresh', () => {
    const cm = new CacheManager(outputDir);
    cm.update('page1', 'hash1', 'tpl1');
    expect(cm.isStale('page1', 'hash1', 'tpl1')).toBe(false);
  });

  it('prunes deleted entries', () => {
    const cm = new CacheManager(outputDir);
    cm.update('page1', 'hash1', 'tpl1');
    cm.update('page2', 'hash2', 'tpl1');
    cm.prune(['page1']);
    expect(cm.isStale('page1', 'hash1', 'tpl1')).toBe(false);
    expect(cm.isStale('page2', 'hash2', 'tpl1')).toBe(true);
  });

  it('clear removes all entries', () => {
    const cm = new CacheManager(outputDir);
    cm.update('page1', 'hash1', 'tpl1');
    cm.save();
    expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(true);

    cm.clear();
    cm.load();
    expect(cm.isStale('page1', 'hash1', 'tpl1')).toBe(true);
    expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(false);
  });

  it('computeHash produces consistent results', () => {
    const h1 = CacheManager.computeHash('hello');
    const h2 = CacheManager.computeHash('hello');
    expect(h1).toBe(h2);
    expect(h1).not.toBe(CacheManager.computeHash('world'));
  });

  it('computeTemplateHashes returns builtin-defaults for missing dir', () => {
    const hash = CacheManager.computeTemplateHashes(path.join(tmpDir, 'nonexistent'));
    expect(hash).toBe('builtin-defaults');
  });

  it('computeTemplateHashes changes when template changes', () => {
    const tplDir = path.join(tmpDir, 'templates');
    fs.mkdirSync(tplDir);
    fs.writeFileSync(path.join(tplDir, 'page.hbs'), '<h1>{{title}}</h1>');

    const h1 = CacheManager.computeTemplateHashes(tplDir);

    fs.writeFileSync(path.join(tplDir, 'page.hbs'), '<h2>{{title}}</h2>');

    const h2 = CacheManager.computeTemplateHashes(tplDir);
    expect(h1).not.toBe(h2);
  });

  it('computeTemplateHashes includes files in subdirectories', () => {
    const tplDir = path.join(tmpDir, 'templates');
    fs.mkdirSync(path.join(tplDir, 'layouts'), { recursive: true });
    fs.mkdirSync(path.join(tplDir, 'partials'), { recursive: true });
    fs.writeFileSync(path.join(tplDir, 'page.hbs'), '<h1>{{title}}</h1>');
    fs.writeFileSync(path.join(tplDir, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');
    fs.writeFileSync(path.join(tplDir, 'partials', 'nav.hbs'), '<nav>Nav</nav>');

    const h1 = CacheManager.computeTemplateHashes(tplDir);

    fs.writeFileSync(path.join(tplDir, 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');

    const h2 = CacheManager.computeTemplateHashes(tplDir);
    expect(h1).not.toBe(h2);
  });

  it('computeTemplateHashes ignores non-hbs files', () => {
    const tplDir = path.join(tmpDir, 'templates');
    fs.mkdirSync(tplDir);
    fs.writeFileSync(path.join(tplDir, 'page.hbs'), '<h1>{{title}}</h1>');
    fs.writeFileSync(path.join(tplDir, 'readme.txt'), 'not a template');

    const h1 = CacheManager.computeTemplateHashes(tplDir);

    fs.writeFileSync(path.join(tplDir, 'readme.txt'), 'changed but not a template');

    const h2 = CacheManager.computeTemplateHashes(tplDir);
    expect(h1).toBe(h2);
  });
});
