import fs from 'fs';
import os from 'os';
import path from 'path';

import { CACHE_FILE_NAME, hashContent, loadCache } from '../cache';
import { createEngine } from '../engine';
import { buildSite } from '../site';
import type { EngineOptions } from '../engine';

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

const PAGE_A = '---\ntitle: Alpha\n---\n# Body A';
const PAGE_B = '---\ntitle: Beta\ntags: [one, two]\n---\n# Body B';

describe('incremental builds', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  const options = (overrides: Partial<EngineOptions> = {}): EngineOptions => ({
    contentDir,
    outputDir,
    templatesDir,
    ...overrides,
  });

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    templatesDir = path.join(root, 'missing-templates');
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('builds every page on the first incremental build and seeds the cache', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    const engine = createEngine(options({ incremental: true }));
    const pages = engine.run();

    expect(pages).toHaveLength(2);
    expect(engine.stats.pagesBuilt).toBe(2);
    expect(engine.stats.pagesSkipped).toBe(0);
    expect(engine.stats.timeSavedMs).toBe(0);
    expect(engine.stats.cacheLoaded).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, CACHE_FILE_NAME))).toBe(true);
  });

  it('skips every unchanged page on a second incremental build', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();
    const aBefore = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    const bBefore = fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8');

    const second = createEngine(options({ incremental: true }));
    second.run();

    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    expect(second.stats.cacheLoaded).toBe(true);
    expect(second.stats.timeSavedMs).toBeGreaterThan(0);

    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toBe(aBefore);
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8')).toBe(bBefore);
  });

  it('rebuilds only the page whose source changed', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();
    const bBefore = fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8');

    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: Alpha v2\n---\n# Body A v2');

    const second = createEngine(options({ incremental: true }));
    second.run();

    expect(second.stats.pagesBuilt).toBe(1);
    expect(second.stats.pagesSkipped).toBe(1);
    expect(second.stats.timeSavedMs).toBeGreaterThan(0);

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(aHtml).toContain('<h1>Alpha v2</h1>');
    expect(aHtml).toContain('<h1>Body A v2</h1>');
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8')).toBe(bBefore);
  });

  it('rebuilds every page when a template changes', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    const tpl = path.join(root, 'templates');
    writeTree(tpl, {
      'default.hbs': '<article>{{title}}</article>',
      'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
    });
    templatesDir = tpl;

    createEngine(options({ incremental: true })).run();

    fs.writeFileSync(path.join(tpl, 'default.hbs'), '<article>{{title}} updated</article>');

    const second = createEngine(options({ incremental: true }));
    second.run();

    expect(second.stats.pagesBuilt).toBe(2);
    expect(second.stats.pagesSkipped).toBe(0);
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toContain(
      '<article>Alpha updated</article>',
    );
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8')).toContain(
      '<article>Beta updated</article>',
    );
  });

  it('rebuilds the index when page metadata changes', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();
    const indexBefore = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexBefore).toContain('Alpha');

    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: Alpha Renamed\n---\n# Body A');

    const second = createEngine(options({ incremental: true }));
    second.run();

    expect(second.stats.pagesBuilt).toBe(1);
    const indexAfter = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexAfter).toContain('Alpha Renamed');
    expect(indexAfter).not.toContain('>Alpha</a>');
  });

  it('does not rebuild the index when nothing changed', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();
    const indexBefore = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');

    const second = createEngine(options({ incremental: true }));
    second.run();

    expect(fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8')).toBe(indexBefore);
  });

  it('--clean discards the cache and rebuilds everything', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    const first = createEngine(options({ incremental: true }));
    first.run();
    expect(first.stats.pagesBuilt).toBe(2);

    const clean = createEngine(options({ incremental: true, clean: true }));
    clean.run();

    expect(clean.stats.pagesBuilt).toBe(2);
    expect(clean.stats.pagesSkipped).toBe(0);
    expect(clean.stats.cacheLoaded).toBe(false);
    expect(fs.existsSync(path.join(outputDir, CACHE_FILE_NAME))).toBe(true);
  });

  it('seeds the cache after a clean build so the next build can skip', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();
    createEngine(options({ incremental: true, clean: true })).run();

    const third = createEngine(options({ incremental: true }));
    third.run();
    expect(third.stats.pagesBuilt).toBe(0);
    expect(third.stats.pagesSkipped).toBe(2);
  });

  it('caches parsed frontmatter and rendered HTML in the manifest', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();

    const manifest = loadCache(path.join(outputDir, CACHE_FILE_NAME));
    expect(manifest).not.toBeNull();

    const entryA = manifest!.entries['a.html'];
    expect(entryA.sourceHash).toBe(hashContent(PAGE_A));
    expect(entryA.page!.data.title).toBe('Alpha');
    expect(entryA.page!.html).toContain('<h1>Body A</h1>');
    expect(entryA.output).toContain('<h1>Alpha</h1>');

    const entryB = manifest!.entries['b.html'];
    expect(entryB.page!.tags).toEqual(['one', 'two']);
  });

  it('produces identical output to a full build when seeded fresh', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    const fullDir = path.join(root, 'full');
    buildSite({ contentDir, outputDir: fullDir, templatesDir });

    const engine = createEngine(options({ incremental: true }));
    engine.run();

    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toBe(
      fs.readFileSync(path.join(fullDir, 'a.html'), 'utf8'),
    );
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8')).toBe(
      fs.readFileSync(path.join(fullDir, 'b.html'), 'utf8'),
    );
    expect(fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8')).toBe(
      fs.readFileSync(path.join(fullDir, 'index.html'), 'utf8'),
    );
  });

  it('does not write a cache file for a regular (non-incremental) build', () => {
    writeTree(contentDir, { 'a.md': PAGE_A });

    buildSite({ contentDir, outputDir, templatesDir });

    expect(fs.existsSync(path.join(outputDir, CACHE_FILE_NAME))).toBe(false);
  });

  it('uses cached pages in the plugin context for skipped pages', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    createEngine(options({ incremental: true })).run();

    let seenTitles: string[] = [];
    const recorder = {
      name: 'recorder',
      afterBuild: (context: { pages: { title: string }[] }) => {
        seenTitles = context.pages.map((page) => page.title);
      },
    };

    const second = createEngine(options({ incremental: true, plugins: [recorder] }));
    second.run();

    expect(second.stats.pagesSkipped).toBe(2);
    expect(seenTitles.sort()).toEqual(['Alpha', 'Beta']);
  });

  it('keeps the plugin lifecycle intact during incremental builds', () => {
    writeTree(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    const events: string[] = [];
    const recorder = {
      name: 'recorder',
      onStart: () => events.push('onStart'),
      beforeBuild: () => events.push('beforeBuild'),
      onFile: (page: { slug: string }) => events.push(`onFile:${page.slug}`),
      afterBuild: () => events.push('afterBuild'),
      onEnd: () => events.push('onEnd'),
    };

    const first = createEngine(options({ incremental: true, plugins: [recorder] }));
    first.run();
    expect(events).toEqual([
      'onStart',
      'beforeBuild',
      'onFile:a',
      'onFile:b',
      'afterBuild',
      'onEnd',
    ]);

    events.length = 0;
    const second = createEngine(options({ incremental: true, plugins: [recorder] }));
    second.run();
    expect(events).toEqual(['onStart', 'beforeBuild', 'afterBuild', 'onEnd']);
    expect(second.stats.pagesSkipped).toBe(2);
  });
});
