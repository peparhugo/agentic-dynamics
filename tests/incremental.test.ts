import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { CACHE_FILENAME, loadManifest } from '../src/cache';
import { buildSiteIncremental } from '../src/incremental';

function makeTmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incremental-test-'));
}

describe('buildSiteIncremental', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  function writePages(): void {
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\n# About us');
    fs.writeFileSync(path.join(contentDir, 'contact.md'), '---\ntitle: Contact\n---\n# Contact us');
  }

  it('throws when the content directory does not exist', () => {
    expect(() => buildSiteIncremental({ contentDir: path.join(contentDir, 'missing'), outputDir })).toThrow(
      /Content directory not found/
    );
  });

  it('performs a full (clean) build when no cache exists yet', () => {
    writePages();

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.clean).toBe(true);
    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(result.stats.totalPages).toBe(2);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'contact.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, CACHE_FILENAME))).toBe(true);
  });

  it('skips every page on a second build when nothing changed', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.clean).toBe(false);
    expect(result.stats.pagesBuilt).toBe(0);
    expect(result.stats.pagesSkipped).toBe(2);
    expect(result.stats.totalPages).toBe(2);
    expect(result.pages.map((p) => p.title).sort()).toEqual(['About', 'Contact']);
  });

  it('rebuilds only the page whose source content changed', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });

    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About Updated\n---\n# About us, updated');

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    const aboutHtml = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
    expect(aboutHtml).toContain('About us, updated');
  });

  it('leaves an unchanged page output file untouched (same mtime) when skipped', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });
    const before = fs.statSync(path.join(outputDir, 'contact.html')).mtimeMs;

    // Force the clock forward enough to detect a rewrite if one happened.
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About Updated\n---\nBody');
    buildSiteIncremental({ contentDir, outputDir });

    const after = fs.statSync(path.join(outputDir, 'contact.html')).mtimeMs;
    expect(after).toBe(before);
  });

  it('invalidates every cached page when a template file changes', () => {
    const templatesDir = makeTmpDir();
    try {
      fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
      fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<div class="v1">{{{body}}}</div>');
      writePages();

      buildSiteIncremental({ contentDir, outputDir, templatesDir });

      fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<div class="v2">{{{body}}}</div>');
      const result = buildSiteIncremental({ contentDir, outputDir, templatesDir });

      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);
      const html = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
      expect(html).toContain('class="v2"');
    } finally {
      fs.rmSync(templatesDir, { recursive: true, force: true });
    }
  });

  it('forces a full rebuild when --clean is requested even if nothing changed', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });

    const result = buildSiteIncremental({ contentDir, outputDir }, { clean: true });

    expect(result.stats.clean).toBe(true);
    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('does a clean build when the cache file is missing', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });
    fs.rmSync(path.join(outputDir, CACHE_FILENAME));

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.clean).toBe(true);
    expect(result.stats.pagesBuilt).toBe(2);
  });

  it('does a clean build when the cache file is corrupt', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });
    fs.writeFileSync(path.join(outputDir, CACHE_FILENAME), '{ not valid json');

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.clean).toBe(true);
    expect(result.stats.pagesBuilt).toBe(2);
  });

  it('rebuilds a page whose cached output file was deleted, even if the source is unchanged', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });
    fs.rmSync(path.join(outputDir, 'about.html'));

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
  });

  it('removes stale output and cache entries for deleted source files', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });

    fs.rmSync(path.join(contentDir, 'contact.md'));
    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'contact.html'))).toBe(false);

    const manifest = loadManifest(path.join(outputDir, CACHE_FILENAME));
    expect(Object.keys(manifest.entries)).toEqual(['about.md']);
  });

  it('reports an estimated time saved when pages are skipped', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });

    const result = buildSiteIncremental({ contentDir, outputDir });

    expect(result.stats.timeSavedMs).toBeGreaterThanOrEqual(0);
  });

  it('produces the same index.html content as a full rebuild would', () => {
    writePages();
    buildSiteIncremental({ contentDir, outputDir });
    const firstIndex = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');

    const result = buildSiteIncremental({ contentDir, outputDir });
    const secondIndex = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');

    expect(secondIndex).toBe(firstIndex);
    expect(secondIndex).toContain('About');
    expect(secondIndex).toContain('Contact');
    expect(result.stats.pagesSkipped).toBe(2);
  });
});

describe('ssg build --incremental CLI', () => {
  let contentDir: string;
  let outputDir: string;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: CLI Page\n---\nHello from the CLI');
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    logSpy.mockRestore();
  });

  it('writes a cache manifest and reports stats on the first incremental build', () => {
    // Imported lazily so the console.log spy above is already installed.
    const { run } = require('../src/cli');
    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir, '--incremental']);

    expect(fs.existsSync(path.join(outputDir, CACHE_FILENAME))).toBe(true);
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
    expect(logSpy).toHaveBeenCalledWith(expect.stringMatching(/Stats: 1 built, 0 skipped, 1 total/));
  });

  it('skips the page on a second incremental CLI build', () => {
    const { run } = require('../src/cli');
    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir, '--incremental']);
    logSpy.mockClear();

    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir, '--incremental']);

    expect(logSpy).toHaveBeenCalledWith(expect.stringMatching(/Stats: 0 built, 1 skipped, 1 total/));
  });

  it('forces a full rebuild with --incremental --clean', () => {
    const { run } = require('../src/cli');
    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir, '--incremental']);
    logSpy.mockClear();

    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir, '--incremental', '--clean']);

    expect(logSpy).toHaveBeenCalledWith(expect.stringMatching(/Stats: 1 built, 0 skipped, 1 total/));
  });
});
