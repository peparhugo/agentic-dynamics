import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';
import { BuildCache, CACHE_FILENAME } from '../src/cache';
import type { Plugin } from '../src/plugin';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('incremental builds', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    root = makeTempDir();
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    templatesDir = path.join(root, 'templates');
    fs.mkdirSync(contentDir, { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('performs a full build and writes a cache manifest on the first incremental run', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nBody b');

    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats).toEqual({ pagesBuilt: 2, pagesSkipped: 0, timeSavedMs: 0 });
    expect(fs.existsSync(path.join(outputDir, CACHE_FILENAME))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(true);
  });

  it('skips every unchanged page on a second incremental run', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nBody b');

    build({ contentDir, outputDir, templatesDir, incremental: true });
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(0);
    expect(result.stats.pagesSkipped).toBe(2);
    expect(result.stats.timeSavedMs).toBeGreaterThanOrEqual(0);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(true);

    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8');
    expect(html).toContain('Body a');
  });

  it('rebuilds only the page whose source changed', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nBody b');

    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a (updated)');

    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8');
    expect(aHtml).toContain('Body a (updated)');
  });

  it('rebuilds every page when a template changes', () => {
    writeFile(templatesDir, 'layouts/default.hbs', '<main>{{{body}}}</main>');
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nBody b');

    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(templatesDir, 'layouts/default.hbs', '<section>{{{body}}}</section>');

    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8');
    expect(aHtml).toContain('<section>');
    expect(aHtml).not.toContain('<main>');
  });

  it('forces a full rebuild with the clean flag', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');

    build({ contentDir, outputDir, templatesDir, incremental: true });

    const result = build({ contentDir, outputDir, templatesDir, incremental: true, clean: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('does not write a cache manifest for non-incremental builds', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');

    build({ contentDir, outputDir, templatesDir });

    expect(fs.existsSync(path.join(outputDir, CACHE_FILENAME))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
  });

  it('detects added pages and prunes removed pages across runs', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');
    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nBody b');
    let result = build({ contentDir, outputDir, templatesDir, incremental: true });
    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    fs.rmSync(path.join(contentDir, 'b.md'));
    result = build({ contentDir, outputDir, templatesDir, incremental: true });
    expect(result.stats.pagesBuilt).toBe(0);
    expect(result.stats.pagesSkipped).toBe(1);
    expect(result.pages.map((p) => p.slug)).toEqual(['a']);

    const cache = new BuildCache(path.join(outputDir, CACHE_FILENAME));
    cache.load();
    expect(cache.getPage('b')).toBeUndefined();
    expect(cache.getPage('a')).toBeDefined();
  });

  it('keeps the plugin pipeline intact during incremental builds', () => {
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');

    const events: string[] = [];
    const recorder: Plugin = {
      name: 'recorder',
      onStart: () => events.push('onStart'),
      beforeBuild: () => events.push('beforeBuild'),
      afterBuild: () => events.push('afterBuild'),
      onEnd: () => events.push('onEnd'),
    };

    build({ contentDir, outputDir, templatesDir, incremental: true, plugins: [recorder] });
    events.length = 0;

    build({ contentDir, outputDir, templatesDir, incremental: true, plugins: [recorder] });

    expect(events).toEqual(['onStart', 'beforeBuild', 'afterBuild', 'onEnd']);
  });
});
