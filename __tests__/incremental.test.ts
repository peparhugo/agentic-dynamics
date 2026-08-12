import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, CacheManager, CACHE_FILE } from '../src/site';
import { SiteEngine } from '../src/engine';
import { readPages } from '../src/markdown';
import { parseArgs, run } from '../src/cli';

interface TempDir {
  dir: string;
  cleanup: () => void;
}

function makeTempDir(): TempDir {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
  return { dir, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

function writeFile(dir: string, relPath: string, content: string): void {
  const full = path.join(dir, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content, 'utf8');
}

function writeContent(contentDir: string): void {
  writeFile(contentDir, 'one.md', '---\ntitle: One\ndate: 2024-01-01\n---\nFirst body.');
  writeFile(contentDir, 'two.md', '---\ntitle: Two\ndate: 2024-02-01\n---\nSecond body.');
}

function writeTemplates(templatesDir: string): void {
  writeFile(
    templatesDir,
    'default.hbs',
    '<article>TPL: {{title}} | {{{html}}}</article>'
  );
}

function cacheFileOf(outDir: string): string {
  return path.join(outDir, CACHE_FILE);
}

describe('parseArgs incremental flags', () => {
  it('parses --incremental', () => {
    const { options } = parseArgs(['build', '--incremental']);
    expect(options.incremental).toBe(true);
    expect(options.clean).toBeUndefined();
  });

  it('parses --clean', () => {
    const { options } = parseArgs(['build', '--clean']);
    expect(options.clean).toBe(true);
  });

  it('parses both flags together', () => {
    const { options } = parseArgs(['build', '--incremental', '--clean']);
    expect(options.incremental).toBe(true);
    expect(options.clean).toBe(true);
  });
});

describe('incremental builds', () => {
  it('builds every page and writes a cache manifest on the first build', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    const result = buildSite(contentDir, outDir, { incremental: true });
    expect(result.pages).toBe(2);
    expect(result.pagesBuilt).toBe(2);
    expect(result.pagesSkipped).toBe(0);
    expect(fs.existsSync(cacheFileOf(outDir))).toBe(true);

    const manifest = JSON.parse(fs.readFileSync(cacheFileOf(outDir), 'utf8'));
    expect(manifest.version).toBe(1);
    expect(Object.keys(manifest.entries)).toContain('one.md');
    cleanup();
  });

  it('skips every page when nothing changed', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    const first = buildSite(contentDir, outDir, { incremental: true });
    const before = fs.readFileSync(path.join(outDir, 'one.html'), 'utf8');

    const second = buildSite(contentDir, outDir, { incremental: true });
    expect(second.pagesBuilt).toBe(0);
    expect(second.pagesSkipped).toBe(2);
    expect(second.pages).toBe(2);
    expect(second.timeSavedMs).toBeGreaterThan(0);

    const after = fs.readFileSync(path.join(outDir, 'one.html'), 'utf8');
    expect(after).toBe(before);
    expect(second.files).toContain('one.html');
    expect(second.files).toContain('index.html');
    cleanup();
  });

  it('rebuilds only the changed page', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });

    writeFile(contentDir, 'one.md', '---\ntitle: One\n---\nUpdated first body.');
    const result = buildSite(contentDir, outDir, { incremental: true });

    expect(result.pagesBuilt).toBe(1);
    expect(result.pagesSkipped).toBe(1);
    expect(fs.readFileSync(path.join(outDir, 'one.html'), 'utf8')).toContain(
      'Updated first body.'
    );
    expect(fs.readFileSync(path.join(outDir, 'two.html'), 'utf8')).toContain(
      'Second body.'
    );
    cleanup();
  });

  it('rebuilds all pages when a template changes', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    const templatesDir = path.join(dir, 'templates');
    writeContent(contentDir);
    writeTemplates(templatesDir);

    buildSite(contentDir, outDir, { incremental: true, templatesDir });
    expect(fs.readFileSync(path.join(outDir, 'one.html'), 'utf8')).toContain('TPL: One');

    writeFile(templatesDir, 'default.hbs', '<article>NEW TPL: {{title}} | {{{html}}}</article>');
    const result = buildSite(contentDir, outDir, {
      incremental: true,
      templatesDir,
    });

    expect(result.pagesBuilt).toBe(2);
    expect(result.pagesSkipped).toBe(0);
    expect(fs.readFileSync(path.join(outDir, 'one.html'), 'utf8')).toContain('NEW TPL: One');
    cleanup();
  });

  it('performs a clean build when the cache manifest is missing', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });
    fs.rmSync(cacheFileOf(outDir));

    const result = buildSite(contentDir, outDir, { incremental: true });
    expect(result.pagesBuilt).toBe(2);
    expect(result.pagesSkipped).toBe(0);
    expect(fs.existsSync(cacheFileOf(outDir))).toBe(true);
    cleanup();
  });

  it('performs a clean build when --clean is passed', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });
    expect(buildSite(contentDir, outDir, { incremental: true }).pagesSkipped).toBe(2);

    const result = buildSite(contentDir, outDir, { incremental: true, clean: true });
    expect(result.pagesBuilt).toBe(2);
    expect(result.pagesSkipped).toBe(0);
    cleanup();
  });

  it('removes the output of deleted pages', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });
    expect(fs.existsSync(path.join(outDir, 'two.html'))).toBe(true);

    fs.rmSync(path.join(contentDir, 'two.md'));
    const result = buildSite(contentDir, outDir, { incremental: true });

    expect(result.pages).toBe(1);
    expect(fs.existsSync(path.join(outDir, 'two.html'))).toBe(false);

    const manifest = JSON.parse(fs.readFileSync(cacheFileOf(outDir), 'utf8'));
    expect(Object.keys(manifest.entries)).not.toContain('two.md');
    cleanup();
  });

  it('removes the stale output when a page slug changes', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });
    expect(fs.existsSync(path.join(outDir, 'one.html'))).toBe(true);

    writeFile(
      contentDir,
      'one.md',
      '---\ntitle: One\nslug: renamed\n---\nFirst body.'
    );
    buildSite(contentDir, outDir, { incremental: true });

    expect(fs.existsSync(path.join(outDir, 'one.html'))).toBe(false);
    expect(fs.existsSync(path.join(outDir, 'renamed.html'))).toBe(true);
    cleanup();
  });

  it('keeps output for unchanged pages valid after another page is edited', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });
    const twoBefore = fs.readFileSync(path.join(outDir, 'two.html'), 'utf8');

    writeFile(contentDir, 'one.md', '---\ntitle: One\n---\nChanged.');
    buildSite(contentDir, outDir, { incremental: true });

    expect(fs.readFileSync(path.join(outDir, 'two.html'), 'utf8')).toBe(twoBefore);
    cleanup();
  });
});

describe('caching', () => {
  it('stores cached rendered HTML and parsed frontmatter in the manifest', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });

    const manifest = JSON.parse(fs.readFileSync(cacheFileOf(outDir), 'utf8'));
    const entry = manifest.entries['one.md'];
    expect(entry).toBeDefined();
    expect(entry.page).toBeDefined();
    expect(entry.page.title).toBe('One');
    expect(entry.page.tags).toEqual([]);
    expect(entry.html).toContain('First body.');
    expect(entry.sourceHash).toMatch(/^[a-f0-9]{64}$/);
    cleanup();
  });

  it('reuses cached frontmatter for unchanged pages', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });

    const cache = new CacheManager(
      cacheFileOf(outDir),
      path.join(dir, 'templates'),
      contentDir,
      outDir
    );
    const pages = readPages(contentDir, cache);
    expect(pages).toHaveLength(2);
    expect(pages.find((p) => p.filePath === 'one.md')?.title).toBe('One');
    cleanup();
  });

  it('invalidates a cached entry when its source changes', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    buildSite(contentDir, outDir, { incremental: true });

    writeFile(contentDir, 'one.md', '---\ntitle: Changed Title\n---\nBody.');
    const cache = new CacheManager(
      cacheFileOf(outDir),
      path.join(dir, 'templates'),
      contentDir,
      outDir
    );
    expect(cache.isUnchanged('one.md')).toBe(false);
    expect(cache.isUnchanged('two.md')).toBe(true);
    cleanup();
  });
});

describe('incremental build via CLI', () => {
  it('reports skipped pages through the build command', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    const spy = jest.spyOn(console, 'log').mockImplementation(() => {});
    let output = '';
    try {
      run(['build', '--content', contentDir, '--output', outDir, '--incremental']);
      run(['build', '--content', contentDir, '--output', outDir, '--incremental']);
      output = spy.mock.calls.map((c) => c.join(' ')).join('\n');
    } finally {
      spy.mockRestore();
      cleanup();
    }
    expect(output).toContain('skipped');
    expect(output).toContain('2 pages');
  });
});

describe('SiteEngine incremental option', () => {
  it('builds incrementally through the engine directly', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    const engine = new SiteEngine({
      contentDir,
      outputDir: outDir,
      incremental: true,
    });
    const first = engine.build();
    expect(first.pagesBuilt).toBe(2);

    const second = engine.build();
    expect(second.pagesBuilt).toBe(0);
    expect(second.pagesSkipped).toBe(2);
    cleanup();
  });

  it('does not skip pages when incremental is not set', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeContent(contentDir);

    const engine = new SiteEngine({ contentDir, outputDir: outDir });
    engine.build();
    const result = engine.build();
    expect(result.pagesBuilt).toBe(2);
    expect(result.pagesSkipped).toBe(0);
    cleanup();
  });
});
