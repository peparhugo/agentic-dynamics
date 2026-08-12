import { SSGEngine } from '../src/engine';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/template';
import { BuildCache, BuildStats } from '../src/cache';
import { SSGOptions } from '../src/plugin';
import fs from 'fs';
import path from 'path';
import os from 'os';

function createContentFile(
  dir: string,
  name: string,
  title: string,
  date: string,
  body: string
): void {
  const content = `---
title: ${title}
date: ${date}
tags:
  - test
---
${body}`;
  fs.writeFileSync(path.join(dir, name), content);
}

function createTemplateDir(templateDir: string): void {
  fs.mkdirSync(path.join(templateDir, 'layouts'), { recursive: true });
  fs.mkdirSync(path.join(templateDir, 'partials'), { recursive: true });

  fs.writeFileSync(
    path.join(templateDir, 'layouts', 'default.hbs'),
    '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{> nav}}{{{body}}}</body></html>'
  );
  fs.writeFileSync(
    path.join(templateDir, 'page.hbs'),
    '<article><h1>{{title}}</h1>{{{content}}}</article>'
  );
  fs.writeFileSync(
    path.join(templateDir, 'index.hbs'),
    '<h1>Index</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>'
  );
  fs.writeFileSync(
    path.join(templateDir, 'partials', 'nav.hbs'),
    '<nav>Home</nav>'
  );
}

describe('incremental build', () => {
  let contentDir: string;
  let outputDir: string;
  let templateDir: string;
  let cachePath: string;

  beforeEach(() => {
    contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-content-'));
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-output-'));
    templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-tpl-'));
    cachePath = path.join(contentDir, '..', `.ssg-cache-${path.basename(contentDir)}.json`);

    createContentFile(
      contentDir,
      'post-one.md',
      'Post One',
      '2024-01-15',
      '# Post One\nContent one.'
    );
    createContentFile(
      contentDir,
      'post-two.md',
      'Post Two',
      '2024-02-20',
      '# Post Two\nContent two.'
    );

    createTemplateDir(templateDir);
  });

  afterEach(() => {
    try {
      fs.rmSync(contentDir, { recursive: true, force: true });
    } catch {}
    try {
      fs.rmSync(outputDir, { recursive: true, force: true });
    } catch {}
    try {
      fs.rmSync(templateDir, { recursive: true, force: true });
    } catch {}
    try {
      if (fs.existsSync(cachePath)) fs.unlinkSync(cachePath);
    } catch {}
  });

  function createEngine(incremental = false, clean = false): SSGEngine {
    const options: SSGOptions = {
      content: contentDir,
      output: outputDir,
      templates: templateDir,
      port: 3000,
      incremental,
      clean,
      cacheFile: cachePath,
    };
    const engine = new SSGEngine(options);
    engine.register(new MarkdownPlugin());
    engine.register(new TemplatePlugin());
    return engine;
  }

  it('performs a full build when not incremental', async () => {
    const engine = createEngine(false, false);
    await engine.build();

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('Post One');
    expect(postOne).toContain('Content one.');

    const postTwo = fs.readFileSync(
      path.join(outputDir, 'post-two.html'),
      'utf-8'
    );
    expect(postTwo).toContain('Post Two');

    const index = fs.readFileSync(
      path.join(outputDir, 'index.html'),
      'utf-8'
    );
    expect(index).toContain('Post One');
    expect(index).toContain('Post Two');
  });

  it('performs a full build with clean flag', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    const engine2 = createEngine(true, true);
    await engine2.build();

    const stats = engine2.stats!;
    expect(stats.pagesBuilt).toBe(2);
    expect(stats.pagesSkipped).toBe(0);
  });

  it('skips unchanged pages on second incremental build', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    const engine2 = createEngine(true, false);
    await engine2.build();

    const stats = engine2.stats!;
    expect(stats.pagesSkipped).toBe(2);
    expect(stats.pagesBuilt).toBe(0);

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('Post One');
  });

  it('rebuilds only changed content file on second build', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    createContentFile(
      contentDir,
      'post-one.md',
      'Post One Updated',
      '2024-01-15',
      '# Updated\nNew content.'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const stats = engine2.stats!;
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(1);

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('Post One Updated');
    expect(postOne).toContain('New content.');

    const postTwo = fs.readFileSync(
      path.join(outputDir, 'post-two.html'),
      'utf-8'
    );
    expect(postTwo).toContain('Post Two');
  });

  it('rebuilds all pages when template changes', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article class="v2"><h1>{{title}}</h1>{{{content}}}</article>'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const stats = engine2.stats!;
    expect(stats.pagesBuilt).toBe(2);
    expect(stats.pagesSkipped).toBe(0);

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('<article class="v2">');
  });

  it('rebuilds all pages when layout template changes', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html><head><title>V2 {{title}}</title></head><body>{{> nav}}{{{body}}}</body></html>'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const stats = engine2.stats!;
    expect(stats.pagesBuilt).toBe(2);
    expect(stats.pagesSkipped).toBe(0);

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('V2 Post One');
  });

  it('rebuilds only when partial template changes', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    fs.writeFileSync(
      path.join(templateDir, 'partials', 'nav.hbs'),
      '<nav>Updated Nav</nav>'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    expect(engine2.stats!.pagesBuilt).toBe(2);
  });

  it('handles new pages added after initial build', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    createContentFile(
      contentDir,
      'post-three.md',
      'Post Three',
      '2024-03-10',
      '# Post Three\nThird content.'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const postThree = fs.readFileSync(
      path.join(outputDir, 'post-three.html'),
      'utf-8'
    );
    expect(postThree).toContain('Post Three');

    const index = fs.readFileSync(
      path.join(outputDir, 'index.html'),
      'utf-8'
    );
    expect(index).toContain('Post Three');
  });

  it('handles removed pages on rebuild', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    fs.unlinkSync(path.join(contentDir, 'post-one.md'));

    const engine2 = createEngine(true, false);
    await engine2.build();

    expect(fs.existsSync(path.join(outputDir, 'post-one.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'post-two.html'))).toBe(true);

    const index = fs.readFileSync(
      path.join(outputDir, 'index.html'),
      'utf-8'
    );
    expect(index).not.toContain('post-one.html');
    expect(index).toContain('post-two.html');
  });

  it('does a full build when cache is missing', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    if (fs.existsSync(cachePath)) fs.unlinkSync(cachePath);

    const engine2 = createEngine(true, false);
    await engine2.build();

    expect(engine2.stats!.pagesBuilt).toBe(2);
    expect(engine2.stats!.pagesSkipped).toBe(0);
  });

  it('produces correct HTML with templates on incremental build', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    const engine2 = createEngine(true, false);
    await engine2.build();

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('Post One');
    expect(postOne).toContain('<article>');
    expect(postOne).toContain('<nav>Home</nav>');
    expect(postOne).toContain('Content one.');
  });

  it('works without template directory (fallback) with incremental flag', async () => {
    const fallbackContent = fs.mkdtempSync(
      path.join(os.tmpdir(), 'ssg-fallback-')
    );
    const fallbackOutput = fs.mkdtempSync(
      path.join(os.tmpdir(), 'ssg-fb-out-')
    );
    const fallbackCache = path.join(fallbackContent, '..', `.ssg-cache-${path.basename(fallbackContent)}.json`);

    createContentFile(
      fallbackContent,
      'hello.md',
      'Hello',
      '2024-01-01',
      '# Hello\nWorld'
    );

    const options: SSGOptions = {
      content: fallbackContent,
      output: fallbackOutput,
      templates: '/nonexistent/templates',
      port: 3000,
      incremental: true,
      cacheFile: fallbackCache,
    };

    const engine = new SSGEngine(options);
    engine.register(new MarkdownPlugin());
    engine.register(new TemplatePlugin());
    await engine.build();

    const html = fs.readFileSync(
      path.join(fallbackOutput, 'hello.html'),
      'utf-8'
    );
    expect(html).toContain('Hello');
    expect(html).toContain('World');

    try { if (fs.existsSync(fallbackCache)) fs.unlinkSync(fallbackCache); } catch {}
    fs.rmSync(fallbackContent, { recursive: true, force: true });
    fs.rmSync(fallbackOutput, { recursive: true, force: true });
  });

  it('tracks build stats correctly', async () => {
    const engine = createEngine(true, false);
    await engine.build();

    const stats = engine.stats!;
    expect(stats.pagesBuilt).toBe(2);
    expect(stats.pagesSkipped).toBe(0);

    const engine2 = createEngine(true, false);
    await engine2.build();

    const stats2 = engine2.stats!;
    expect(stats2.pagesBuilt).toBe(0);
    expect(stats2.pagesSkipped).toBe(2);
  });

  it('reports stats in combined scenario (one changed, one unchanged)', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    createContentFile(
      contentDir,
      'post-one.md',
      'Post One Changed',
      '2024-01-15',
      '# Changed'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    expect(engine2.stats!.pagesBuilt).toBe(1);
    expect(engine2.stats!.pagesSkipped).toBe(1);
  });

  it('handles empty content directory', async () => {
    const emptyContent = fs.mkdtempSync(
      path.join(os.tmpdir(), 'ssg-empty-')
    );
    const emptyOutput = fs.mkdtempSync(
      path.join(os.tmpdir(), 'ssg-empty-out-')
    );
    const emptyCache = path.join(emptyContent, '..', `.ssg-cache-${path.basename(emptyContent)}.json`);

    const options: SSGOptions = {
      content: emptyContent,
      output: emptyOutput,
      templates: templateDir,
      port: 3000,
      incremental: true,
      cacheFile: emptyCache,
    };

    const engine = new SSGEngine(options);
    engine.register(new MarkdownPlugin());
    engine.register(new TemplatePlugin());
    await engine.build();

    const indexPath = path.join(emptyOutput, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    try { if (fs.existsSync(emptyCache)) fs.unlinkSync(emptyCache); } catch {}
    fs.rmSync(emptyContent, { recursive: true, force: true });
    fs.rmSync(emptyOutput, { recursive: true, force: true });
  });

  it('caches parsed frontmatter', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    const cache = new BuildCache(cachePath);
    const loaded = cache.load();

    expect(loaded).toBe(true);
    expect(cache.isPopulated()).toBe(true);
    expect(cache.getCachedPage('post-one')).toBeTruthy();
    expect(cache.getCachedPage('post-two')).toBeTruthy();
  });

  it('invalidates cache entry when source changes', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    createContentFile(
      contentDir,
      'post-one.md',
      'Modified Post One',
      '2024-01-15',
      '# Modified content'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('Modified Post One');
  });

  it('invalidates cache entry when template changes during second build', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article class="updated"><h1>{{title}}</h1>{{{content}}}</article>'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('class="updated"');
  });

  it('rebuilds index even when no page content changes', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    const eng1Index = fs.readFileSync(
      path.join(outputDir, 'index.html'),
      'utf-8'
    );

    const engine2 = createEngine(true, false);
    await engine2.build();

    const eng2Index = fs.readFileSync(
      path.join(outputDir, 'index.html'),
      'utf-8'
    );
    expect(eng2Index).toBe(eng1Index);
  });

  it('incremental build with only one page', async () => {
    fs.unlinkSync(path.join(contentDir, 'post-two.md'));

    const engine1 = createEngine(true, false);
    await engine1.build();
    expect(engine1.stats!.pagesBuilt).toBe(1);

    const engine2 = createEngine(true, false);
    await engine2.build();
    expect(engine2.stats!.pagesBuilt).toBe(0);
    expect(engine2.stats!.pagesSkipped).toBe(1);
  });

  it('incremental build preserves content across multiple builds', async () => {
    const engine1 = createEngine(true, false);
    await engine1.build();

    const engine2 = createEngine(true, false);
    await engine2.build();

    const engine3 = createEngine(true, false);
    await engine3.build();

    expect(engine2.stats!.pagesSkipped).toBe(2);
    expect(engine3.stats!.pagesSkipped).toBe(2);

    const postOne = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOne).toContain('Post One');
    expect(postOne).toContain('Content one.');
  });
});

describe('BuildCache', () => {
  it('computes consistent hashes', () => {
    const hash1 = BuildCache.computeHash('hello world');
    const hash2 = BuildCache.computeHash('hello world');
    expect(hash1).toBe(hash2);
  });

  it('computes different hashes for different content', () => {
    const hash1 = BuildCache.computeHash('hello world');
    const hash2 = BuildCache.computeHash('hello world!');
    expect(hash1).not.toBe(hash2);
  });

  it('computes file hash correctly', () => {
    const tmpFile = path.join(os.tmpdir(), 'ssg-cache-test.txt');
    fs.writeFileSync(tmpFile, 'test content');
    const hash = BuildCache.computeFileHash(tmpFile);
    expect(hash).toBe(BuildCache.computeHash('test content'));
    fs.unlinkSync(tmpFile);
  });

  it('computes template hash from directory', () => {
    const tplDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-hash-'));
    fs.mkdirSync(path.join(tplDir, 'layouts'), { recursive: true });
    fs.writeFileSync(
      path.join(tplDir, 'page.hbs'),
      '<h1>{{title}}</h1>'
    );
    fs.writeFileSync(
      path.join(tplDir, 'layouts', 'default.hbs'),
      '<html>{{{body}}}</html>'
    );

    const hash1 = BuildCache.computeTemplateHash(tplDir);
    const hash2 = BuildCache.computeTemplateHash(tplDir);
    expect(hash1).toBe(hash2);
    expect(hash1).toBeTruthy();

    fs.writeFileSync(
      path.join(tplDir, 'page.hbs'),
      '<h2>{{title}}</h2>'
    );
    const hash3 = BuildCache.computeTemplateHash(tplDir);
    expect(hash3).not.toBe(hash1);

    fs.rmSync(tplDir, { recursive: true, force: true });
  });

  it('computes empty hash for non-existent template dir', () => {
    const hash = BuildCache.computeTemplateHash('/nonexistent/dir');
    expect(hash).toBe('');
  });

  it('save and load cache manifest', () => {
    const cacheFile = path.join(os.tmpdir(), '.ssg-test-cache.json');

    const cache = new BuildCache(cacheFile);
    cache.clear();
    cache.load();

    cache.setContentHash('test.md', 'abc123');
    cache.setTemplateHash('def456');
    cache.setCachedPage('test', {
      page: {
        frontmatter: { title: 'Test', date: '', tags: [] },
        html: '<p>test</p>',
        slug: 'test',
      },
      html: '<html>test</html>',
    });
    cache.setIndexHtml('<html>index</html>');
    cache.save();

    const cache2 = new BuildCache(cacheFile);
    cache2.load();
    expect(cache2.isPopulated()).toBe(true);
    expect(cache2.getContentHash('test.md')).toBe('abc123');
    expect(cache2.getTemplateHash()).toBe('def456');
    expect(cache2.getCachedPage('test')).toBeTruthy();
    expect(cache2.getCachedPage('test')!.html).toBe('<html>test</html>');
    expect(cache2.getIndexHtml()).toBe('<html>index</html>');

    fs.unlinkSync(cacheFile);
  });

  it('clear removes all cache data', () => {
    const cacheFile = path.join(os.tmpdir(), '.ssg-test-clear.json');

    const cache = new BuildCache(cacheFile);
    cache.load();
    cache.setContentHash('test.md', 'abc123');
    cache.setTemplateHash('def456');
    cache.save();

    expect(fs.existsSync(cacheFile)).toBe(true);

    cache.clear();
    expect(fs.existsSync(cacheFile)).toBe(false);
    expect(cache.isPopulated()).toBe(false);

    cache.load();
    expect(cache.getContentHash('test.md')).toBeUndefined();
    expect(cache.getTemplateHash()).toBe('');

    try { fs.unlinkSync(cacheFile); } catch {}
  });

  it('load returns false for missing cache file', () => {
    const cache = new BuildCache('/nonexistent/cache.json');
    const loaded = cache.load();
    expect(loaded).toBe(false);
    expect(cache.isPopulated()).toBe(false);
  });
});
