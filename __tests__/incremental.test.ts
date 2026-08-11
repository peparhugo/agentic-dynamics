import fs from 'fs';
import path from 'path';
import { generateSite, parseMarkdownFile } from '../src/generator';
import { BuildCache, hashFile, hashDirectoryTemplates } from '../src/cache';

const tmpDir = path.join(__dirname, '..', '.test-tmp-inc');

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

function createContentDir(name: string): string {
  const dir = path.join(tmpDir, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

function createTemplatesDir(name: string): string {
  const dir = path.join(tmpDir, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function fileMtime(outputDir: string, name: string): number {
  const p = path.join(outputDir, name);
  if (!fs.existsSync(p)) return 0;
  return fs.statSync(p).mtimeMs;
}

function setOldMtime(outputDir: string, name: string): void {
  const p = path.join(outputDir, name);
  if (fs.existsSync(p)) {
    fs.utimesSync(p, 0, 0);
  }
}

describe('BuildCache', () => {
  it('computes consistent file hashes', () => {
    const dir = createContentDir('hash-test');
    const fp = writeFile(dir, 'test.md', '# Hello');
    const h1 = hashFile(fp);
    const h2 = hashFile(fp);
    expect(h1).toBe(h2);
    expect(h1).toHaveLength(32);
  });

  it('detects changed vs unchanged files', () => {
    const contentDir = createContentDir('cache-detect');
    const outputDir = path.join(tmpDir, 'cache-detect-out');
    const fp = writeFile(contentDir, 'page.md', '---\ntitle: Test\n---\nContent.');
    const page = parseMarkdownFile(fp);
    writeFile(outputDir, `${page!.slug}.html`, '<html></html>');

    const cache = new BuildCache(contentDir, outputDir);
    cache.load();
    cache.updateManifest(fp, 'page');
    cache.persist();

    const cache2 = new BuildCache(contentDir, outputDir);
    cache2.load();
    expect(cache2.hasValidManifest()).toBe(true);
    expect(cache2.shouldSkipFile(fp, 'page')).toBe(true);

    writeFile(contentDir, 'page.md', '---\ntitle: Changed\n---\nNew content.');
    expect(cache2.shouldSkipFile(fp, 'page')).toBe(false);
  });

  it('detects changed template hashes', () => {
    const contentDir = createContentDir('cache-tpl');
    const outputDir = path.join(tmpDir, 'cache-tpl-out');
    const templatesDir = createTemplatesDir('cache-tpl-tpl');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    writeFile(layoutsDir, 'default.hbs', '<html><body>{{{body}}}</body></html>');

    const fp = writeFile(contentDir, 'page.md', '---\ntitle: Test\n---\nContent.');
    const page = parseMarkdownFile(fp);
    writeFile(outputDir, `${page!.slug}.html`, '<html></html>');

    const cache = new BuildCache(contentDir, outputDir, templatesDir);
    cache.load();
    cache.updateManifest(fp, 'page');
    cache.finalize();
    cache.persist();

    const cache2 = new BuildCache(contentDir, outputDir, templatesDir);
    cache2.load();
    expect(cache2.shouldSkipFile(fp, 'page')).toBe(true);

    writeFile(layoutsDir, 'default.hbs', '<html><body>CHANGED{{{body}}}</body></html>');

    const cache3 = new BuildCache(contentDir, outputDir, templatesDir);
    cache3.load();
    expect(cache3.shouldSkipFile(fp, 'page')).toBe(false);
  });

  it('clear removes manifest file', () => {
    const contentDir = createContentDir('cache-clear');
    const outputDir = path.join(tmpDir, 'cache-clear-out');
    const fp = writeFile(contentDir, 'page.md', '---\ntitle: Test\n---\nContent.');
    const page = parseMarkdownFile(fp);
    writeFile(outputDir, `${page!.slug}.html`, '<html></html>');

    const cache = new BuildCache(contentDir, outputDir);
    cache.load();
    cache.updateManifest(fp, 'page');
    cache.persist();

    expect(fs.existsSync(path.join(contentDir, '.ssg-cache.json'))).toBe(true);

    cache.clear();
    expect(fs.existsSync(path.join(contentDir, '.ssg-cache.json'))).toBe(false);
  });

  it('handles corrupted manifest gracefully', () => {
    const contentDir = createContentDir('cache-corrupt');
    const corruptPath = path.join(contentDir, '.ssg-cache.json');
    fs.writeFileSync(corruptPath, 'not valid json {{{');

    const cache = new BuildCache(contentDir, path.join(tmpDir, 'cache-corrupt-out'));
    cache.load();
    expect(cache.hasValidManifest()).toBe(false);
  });
});

describe('hashDirectoryTemplates', () => {
  it('returns same hash for unchanged templates', () => {
    const dir = createTemplatesDir('hash-tpl-test');
    const layoutsDir = path.join(dir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    writeFile(layoutsDir, 'default.hbs', '<html>{{{body}}}</html>');

    const h1 = hashDirectoryTemplates(dir);
    const h2 = hashDirectoryTemplates(dir);
    expect(h1).toBeTruthy();
    expect(h1).toBe(h2);
  });

  it('returns different hash when template changes', () => {
    const dir = createTemplatesDir('hash-tpl-chg');
    const layoutsDir = path.join(dir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    writeFile(layoutsDir, 'default.hbs', '<html>{{{body}}}</html>');

    const h1 = hashDirectoryTemplates(dir);

    writeFile(layoutsDir, 'default.hbs', '<html><body>{{{body}}}</body></html>');
    const h2 = hashDirectoryTemplates(dir);

    expect(h1).not.toBe(h2);
  });

  it('returns empty string for nonexistent directory', () => {
    expect(hashDirectoryTemplates('/nonexistent/path')).toBe('');
  });
});

describe('incremental build (no templates)', () => {
  it('first incremental build creates manifest and does full build', () => {
    const contentDir = createContentDir('inc-first');
    const outputDir = path.join(tmpDir, 'inc-first-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    const count = generateSite(contentDir, outputDir, undefined, { incremental: true });
    expect(count).toBe(3);

    expect(fs.existsSync(path.join(contentDir, '.ssg-cache.json'))).toBe(true);
    const manifest = JSON.parse(fs.readFileSync(path.join(contentDir, '.ssg-cache.json'), 'utf-8'));
    expect(manifest.pages).toBeDefined();
    expect(Object.keys(manifest.pages)).toHaveLength(2);
    expect(manifest.pages['a']).toBeDefined();
    expect(manifest.pages['b']).toBeDefined();
  });

  it('skips unchanged pages on second build', () => {
    const contentDir = createContentDir('inc-skip');
    const outputDir = path.join(tmpDir, 'inc-skip-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    setOldMtime(outputDir, 'a.html');
    setOldMtime(outputDir, 'b.html');
    setOldMtime(outputDir, 'index.html');

    // second build — nothing changed
    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const mtimeA2 = fileMtime(outputDir, 'a.html');
    const mtimeB2 = fileMtime(outputDir, 'b.html');
    const mtimeIdx2 = fileMtime(outputDir, 'index.html');

    expect(mtimeA2).toBe(0); // skipped
    expect(mtimeB2).toBe(0); // skipped
    // index is always rebuilt
    expect(mtimeIdx2).toBeGreaterThan(0);
  });

  it('rebuilds only changed page', () => {
    const contentDir = createContentDir('inc-changed');
    const outputDir = path.join(tmpDir, 'inc-changed-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    setOldMtime(outputDir, 'a.html');
    setOldMtime(outputDir, 'b.html');

    writeFile(contentDir, 'a.md', '---\ntitle: A Updated\n---\nContent A modified');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const mtimeA2 = fileMtime(outputDir, 'a.html');
    const mtimeB2 = fileMtime(outputDir, 'b.html');

    expect(mtimeA2).toBeGreaterThan(0); // rebuilt
    expect(mtimeB2).toBe(0); // unchanged

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8');
    expect(aHtml).toContain('A Updated');
    expect(aHtml).toContain('Content A modified');
  });

  it('rebuilds page when output file is missing', () => {
    const contentDir = createContentDir('inc-missing-out');
    const outputDir = path.join(tmpDir, 'inc-missing-out-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    // Delete output file for b
    fs.unlinkSync(path.join(outputDir, 'b.html'));

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(true);
    // b should have been rebuilt since its output was missing
    const bHtml = fs.readFileSync(path.join(outputDir, 'b.html'), 'utf-8');
    expect(bHtml).toContain('Content B');
  });

  it('detects new pages added after first build', () => {
    const contentDir = createContentDir('inc-new-page');
    const outputDir = path.join(tmpDir, 'inc-new-page-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');

    generateSite(contentDir, outputDir, undefined, { incremental: true });
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'c.html'))).toBe(false);

    writeFile(contentDir, 'c.md', '---\ntitle: C\n---\nContent C');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    expect(fs.existsSync(path.join(outputDir, 'c.html'))).toBe(true);
    const cHtml = fs.readFileSync(path.join(outputDir, 'c.html'), 'utf-8');
    expect(cHtml).toContain('Content C');

    // manifest should now have c
    const manifest = JSON.parse(fs.readFileSync(path.join(contentDir, '.ssg-cache.json'), 'utf-8'));
    expect(manifest.pages['c']).toBeDefined();
  });

  it('removes stale entries for deleted pages', () => {
    const contentDir = createContentDir('inc-deleted');
    const outputDir = path.join(tmpDir, 'inc-deleted-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const manifest1 = JSON.parse(fs.readFileSync(path.join(contentDir, '.ssg-cache.json'), 'utf-8'));
    expect(manifest1.pages['b']).toBeDefined();

    // Delete b.md
    fs.unlinkSync(path.join(contentDir, 'b.md'));

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const manifest2 = JSON.parse(fs.readFileSync(path.join(contentDir, '.ssg-cache.json'), 'utf-8'));
    expect(manifest2.pages['a']).toBeDefined();
    expect(manifest2.pages['b']).toBeUndefined();
  });

  it('--clean flag forces full rebuild ignoring cache', () => {
    const contentDir = createContentDir('inc-clean');
    const outputDir = path.join(tmpDir, 'inc-clean-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    setOldMtime(outputDir, 'a.html');
    expect(fs.existsSync(path.join(contentDir, '.ssg-cache.json'))).toBe(true);

    generateSite(contentDir, outputDir, undefined, { incremental: true, clean: true });

    const mtimeA2 = fileMtime(outputDir, 'a.html');
    expect(mtimeA2).toBeGreaterThan(0); // rebuilt

    // manifest should be recreated
    expect(fs.existsSync(path.join(contentDir, '.ssg-cache.json'))).toBe(true);
    const manifest = JSON.parse(fs.readFileSync(path.join(contentDir, '.ssg-cache.json'), 'utf-8'));
    expect(manifest.pages['a']).toBeDefined();
  });

  it('non-incremental build does not create manifest', () => {
    const contentDir = createContentDir('inc-non');
    const outputDir = path.join(tmpDir, 'inc-non-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');

    generateSite(contentDir, outputDir);

    expect(fs.existsSync(path.join(contentDir, '.ssg-cache.json'))).toBe(false);
  });
});

describe('incremental build with templates', () => {
  it('template change triggers rebuild of all pages', () => {
    const contentDir = createContentDir('inc-tpl-content');
    const outputDir = path.join(tmpDir, 'inc-tpl-out');
    const templatesDir = createTemplatesDir('inc-tpl-templates');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    writeFile(layoutsDir, 'default.hbs', '<html><body>{{{body}}}</body></html>');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    generateSite(contentDir, outputDir, templatesDir, { incremental: true });

    setOldMtime(outputDir, 'a.html');
    setOldMtime(outputDir, 'b.html');

    writeFile(layoutsDir, 'default.hbs', '<html><body>CHANGED{{{body}}}</body></html>');

    generateSite(contentDir, outputDir, templatesDir, { incremental: true });

    const mtimeA2 = fileMtime(outputDir, 'a.html');
    const mtimeB2 = fileMtime(outputDir, 'b.html');

    expect(mtimeA2).toBeGreaterThan(0);
    expect(mtimeB2).toBeGreaterThan(0);

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8');
    expect(aHtml).toContain('CHANGED');
  });

  it('index is always rebuilt even with incremental', () => {
    const contentDir = createContentDir('inc-idx-rebuild');
    const outputDir = path.join(tmpDir, 'inc-idx-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    setOldMtime(outputDir, 'index.html');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const mtimeIdx2 = fileMtime(outputDir, 'index.html');
    expect(mtimeIdx2).toBeGreaterThan(0);
  });

  it('index references newly added pages', () => {
    const contentDir = createContentDir('inc-idx-new');
    const outputDir = path.join(tmpDir, 'inc-idx-new-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');

    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const idx1 = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(idx1).toContain('>A<');
    expect(idx1).not.toContain('>C<');

    writeFile(contentDir, 'c.md', '---\ntitle: C\n---\nContent C');
    generateSite(contentDir, outputDir, undefined, { incremental: true });

    const idx2 = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(idx2).toContain('>A<');
    expect(idx2).toContain('>C<');
  });
});

describe('incremental build stats', () => {
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  it('reports stats after each incremental build', () => {
    const contentDir = createContentDir('inc-stats');
    const outputDir = path.join(tmpDir, 'inc-stats-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nContent B');

    // First build — 2 pages + 1 index = 3 built, 0 skipped
    generateSite(contentDir, outputDir, undefined, { incremental: true });

    let statCalls = consoleLogSpy.mock.calls.filter((c: string[]) =>
      c[0] && c[0].includes('Build stats:')
    );
    expect(statCalls.length).toBe(1);
    expect(statCalls[0][0]).toMatch(/3 built/);
    expect(statCalls[0][0]).toMatch(/0 skipped/);

    // Second build — nothing changed: 1 index built, 2 pages skipped
    generateSite(contentDir, outputDir, undefined, { incremental: true });

    statCalls = consoleLogSpy.mock.calls.filter((c: string[]) =>
      c[0] && c[0].includes('Build stats:')
    );
    expect(statCalls.length).toBe(2);
    expect(statCalls[1][0]).toMatch(/1 built/);
    expect(statCalls[1][0]).toMatch(/2 skipped/);

    // Third build — modify one file: 1 page + 1 index = 2 built, 1 skipped
    writeFile(contentDir, 'a.md', '---\ntitle: A New\n---\nContent A modified');
    generateSite(contentDir, outputDir, undefined, { incremental: true });

    statCalls = consoleLogSpy.mock.calls.filter((c: string[]) =>
      c[0] && c[0].includes('Build stats:')
    );
    expect(statCalls.length).toBe(3);
    expect(statCalls[2][0]).toMatch(/2 built/);
    expect(statCalls[2][0]).toMatch(/1 skipped/);
  });

  it('non-incremental build does not show stats', () => {
    const contentDir = createContentDir('inc-no-stats');
    const outputDir = path.join(tmpDir, 'inc-no-stats-out');

    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nContent A');

    generateSite(contentDir, outputDir);

    const statCalls = consoleLogSpy.mock.calls.filter((c: string[]) =>
      c[0] && c[0].includes('Build stats:')
    );
    expect(statCalls.length).toBe(0);
  });
});
