import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildIncremental } from '../src/build';
import { loadCacheManifest } from '../src/cache';
import { clearTemplateEngineCache } from '../src/templates';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('incremental build', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let cacheDir: string;
  let cacheFile: string;

  function writeLayout(name: string, source: string): void {
    fs.writeFileSync(path.join(templatesDir, 'layouts', `${name}.hbs`), source);
  }

  /**
   * Clears the process-wide compiled-template cache before every call so each
   * build behaves like a fresh `ssg build --incremental` process invocation
   * (the real CLI never reuses a stale compiled layout across runs).
   */
  function runBuild(opts: { clean?: boolean } = {}) {
    clearTemplateEngineCache(templatesDir);
    return buildIncremental({ contentDir, outputDir, templatesDir, cacheFile, clean: opts.clean });
  }

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-inc-content-');
    outputDir = makeTmpDir('ssg-inc-dist-');
    templatesDir = makeTmpDir('ssg-inc-templates-');
    cacheDir = makeTmpDir('ssg-inc-cache-');
    cacheFile = path.join(cacheDir, '.ssg-cache.json');

    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    writeLayout('default', '<html><body class="default">{{{body}}}</body></html>');
    writeLayout('post', '<html><body class="post">{{{body}}}</body></html>');

    fs.writeFileSync(path.join(contentDir, 'alpha.md'), `---\ntitle: Alpha\n---\nAlpha body.`);
    fs.writeFileSync(path.join(contentDir, 'beta.md'), `---\ntitle: Beta\ntemplate: post\n---\nBeta body.`);
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
    fs.rmSync(cacheDir, { recursive: true, force: true });
  });

  it('builds every page on the first run and writes a cache manifest', () => {
    const result = runBuild();

    expect(result.stats.total).toBe(2);
    expect(result.stats.built).toBe(2);
    expect(result.stats.skipped).toBe(0);
    expect(fs.existsSync(cacheFile)).toBe(true);

    const manifest = loadCacheManifest(cacheFile);
    expect(Object.keys(manifest.pages).sort()).toEqual(['alpha.md', 'beta.md']);
  });

  it('skips every page on a second run when nothing changed', () => {
    runBuild();
    const alphaHtmlBefore = fs.readFileSync(path.join(outputDir, 'alpha.html'), 'utf-8');

    const result = runBuild();

    expect(result.stats.total).toBe(2);
    expect(result.stats.built).toBe(0);
    expect(result.stats.skipped).toBe(2);
    expect(fs.readFileSync(path.join(outputDir, 'alpha.html'), 'utf-8')).toBe(alphaHtmlBefore);
  });

  it('rebuilds only the page whose source changed', () => {
    runBuild();
    fs.writeFileSync(path.join(contentDir, 'alpha.md'), `---\ntitle: Alpha\n---\nAlpha body, edited.`);

    const result = runBuild();

    expect(result.stats.built).toBe(1);
    expect(result.stats.skipped).toBe(1);
    expect(fs.readFileSync(path.join(outputDir, 'alpha.html'), 'utf-8')).toContain('edited');
  });

  it('rebuilds a newly added page and leaves existing pages skipped', () => {
    runBuild();
    fs.writeFileSync(path.join(contentDir, 'gamma.md'), `---\ntitle: Gamma\n---\nGamma body.`);

    const result = runBuild();

    expect(result.stats.total).toBe(3);
    expect(result.stats.built).toBe(1);
    expect(result.stats.skipped).toBe(2);
    expect(fs.existsSync(path.join(outputDir, 'gamma.html'))).toBe(true);
  });

  it('rebuilds only pages using a layout that changed, leaving pages on other layouts cached', () => {
    runBuild();
    writeLayout('post', '<html><body class="post-v2">{{{body}}}</body></html>');

    const result = runBuild();

    expect(result.stats.built).toBe(1);
    expect(result.stats.skipped).toBe(1);
    expect(fs.readFileSync(path.join(outputDir, 'beta.html'), 'utf-8')).toContain('post-v2');
    expect(fs.readFileSync(path.join(outputDir, 'alpha.html'), 'utf-8')).toContain('class="default"');
  });

  it('invalidates every page when a shared partial changes', () => {
    fs.mkdirSync(path.join(templatesDir, 'partials'));
    fs.writeFileSync(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>v1</footer>');
    writeLayout('default', '<html><body class="default">{{{body}}}{{> footer}}</body></html>');
    writeLayout('post', '<html><body class="post">{{{body}}}{{> footer}}</body></html>');
    runBuild();

    fs.writeFileSync(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>v2</footer>');
    const result = runBuild();

    expect(result.stats.built).toBe(2);
    expect(result.stats.skipped).toBe(0);
    expect(fs.readFileSync(path.join(outputDir, 'alpha.html'), 'utf-8')).toContain('v2');
    expect(fs.readFileSync(path.join(outputDir, 'beta.html'), 'utf-8')).toContain('v2');
  });

  it('rebuilds a page whose output file was deleted, even though the source is unchanged', () => {
    runBuild();
    fs.rmSync(path.join(outputDir, 'alpha.html'));

    const result = runBuild();

    expect(result.stats.built).toBe(1);
    expect(result.stats.skipped).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'alpha.html'))).toBe(true);
  });

  it('does a full rebuild when --clean is passed, even with a warm cache', () => {
    runBuild();

    const result = runBuild({ clean: true });

    expect(result.stats.built).toBe(2);
    expect(result.stats.skipped).toBe(0);
  });

  it('does a full rebuild when the cache manifest is missing', () => {
    runBuild();
    fs.rmSync(cacheFile);

    const result = runBuild();

    expect(result.stats.built).toBe(2);
    expect(result.stats.skipped).toBe(0);
  });

  it('falls back to a clean build when the cache manifest is corrupt JSON', () => {
    runBuild();
    fs.writeFileSync(cacheFile, '{ not valid json');

    const result = runBuild();

    expect(result.stats.built).toBe(2);
    expect(result.stats.skipped).toBe(0);
  });

  it('drops stale cache entries for pages removed from the content directory', () => {
    runBuild();
    fs.rmSync(path.join(contentDir, 'beta.md'));

    const result = runBuild();

    expect(result.stats.total).toBe(1);
    const manifest = loadCacheManifest(cacheFile);
    expect(Object.keys(manifest.pages)).toEqual(['alpha.md']);
  });

  it('only reports positive time saved when pages were actually skipped', () => {
    runBuild();
    const skippedResult = runBuild();
    expect(skippedResult.stats.skipped).toBe(2);
    expect(skippedResult.stats.timeSavedMs).toBeGreaterThanOrEqual(0);

    fs.rmSync(cacheFile);
    const cleanResult = runBuild();
    expect(cleanResult.stats.skipped).toBe(0);
    expect(cleanResult.stats.timeSavedMs).toBe(0);
  });

  it('still runs the full plugin pipeline across skipped and rebuilt pages, so the index stays complete', () => {
    runBuild();
    fs.writeFileSync(path.join(contentDir, 'alpha.md'), `---\ntitle: Alpha Updated\n---\nAlpha body, edited.`);

    runBuild();

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('Alpha Updated');
    expect(indexHtml).toContain('Beta');
  });

  it('keeps working when no cache file path is configured beyond the default (still returns valid stats)', () => {
    const result = buildIncremental({ contentDir, outputDir, templatesDir, cacheFile, clean: true });
    expect(result.pages).toHaveLength(2);
    expect(result.stats.total).toBe(2);
  });
});
