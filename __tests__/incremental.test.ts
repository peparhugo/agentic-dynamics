import { spawnSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, buildSiteWithResult } from '../src/generator';
import { CACHE_FILE_NAME, loadBuildCache, saveBuildCache } from '../src/cache';
import { parseArgs } from '../src/cli';

const REPO_ROOT = path.resolve(__dirname, '..');
const CLI_JS = path.join(REPO_ROOT, 'dist', 'cli.js');

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(dir, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content);
  }
}

function cachePath(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE_NAME);
}

function readCache(outputDir: string): ReturnType<typeof loadBuildCache> {
  return loadBuildCache(cachePath(outputDir));
}

function fixture() {
  const tmp = makeTempDir('ssg-inc-');
  const contentDir = path.join(tmp, 'content');
  const outputDir = path.join(tmp, 'dist');
  writeContent(contentDir, {
    'one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n\n# One\n\nBody **one**.',
    'two.md': '---\ntitle: Two\nauthor: Jane\ntags: [a, b]\n---\n\n# Two\n\nPlain text.',
  });
  return { tmp, contentDir, outputDir };
}

function ensureBuilt(): void {
  if (!fs.existsSync(CLI_JS)) {
    const result = spawnSync('npx', ['tsc'], { cwd: REPO_ROOT, encoding: 'utf8' });
    if (result.status !== 0) {
      throw new Error(`Failed to build TypeScript: ${result.stderr}`);
    }
  }
}

describe('incremental build correctness', () => {
  it('first incremental build is a clean build and writes a cache manifest', () => {
    const { contentDir, outputDir } = fixture();
    const { pages, stats } = buildSiteWithResult({ contentDir, outputDir, incremental: true });

    expect(stats.total).toBe(2);
    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(stats.timeSavedMs).toBe(0);
    expect(stats.cacheLoaded).toBe(false);
    expect(pages.map((p) => p.slug).sort()).toEqual(['one', 'two']);

    expect(fs.existsSync(cachePath(outputDir))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'one.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'two.html'))).toBe(true);
  });

  it('second build with no changes skips every page and reuses output', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });
    const before = fs.readFileSync(path.join(outputDir, 'one.html'), 'utf8');

    const { stats } = buildSiteWithResult({ contentDir, outputDir, incremental: true });

    expect(stats.total).toBe(2);
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(2);
    expect(stats.timeSavedMs).toBeGreaterThan(0);
    expect(stats.cacheLoaded).toBe(true);

    const after = fs.readFileSync(path.join(outputDir, 'one.html'), 'utf8');
    expect(after).toBe(before);
    expect(after).toContain('<title>One</title>');
  });

  it('changing one source file rebuilds only that page', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });

    writeContent(contentDir, {
      'one.md': '---\ntitle: One v2\n---\n\n# One updated\n',
    });
    const { stats, pages } = buildSiteWithResult({ contentDir, outputDir, incremental: true });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(1);

    const one = pages.find((p) => p.slug === 'one');
    expect(one?.title).toBe('One v2');
    expect(fs.readFileSync(path.join(outputDir, 'one.html'), 'utf8')).toContain('One v2');
    expect(fs.readFileSync(path.join(outputDir, 'two.html'), 'utf8')).toContain('<title>Two</title>');
  });

  it('preserves parsed frontmatter for skipped pages', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });

    const { pages } = buildSiteWithResult({ contentDir, outputDir, incremental: true });
    const two = pages.find((p) => p.slug === 'two');
    expect(two?.title).toBe('Two');
    expect(two?.data?.['author']).toBe('Jane');
    expect(two?.tags).toEqual(['a', 'b']);
  });

  it('invalidates every cached page when a template file changes', () => {
    const tmp = makeTempDir('ssg-inc-tpl-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    const tplDir = path.join(tmp, 'templates');
    writeContent(tplDir, {
      'default.hbs': '<h1>{{title}}</h1>\n{{{contentHtml}}}',
    });
    writeContent(contentDir, {
      'a.md': '---\ntitle: A\n---\n\n# A',
      'b.md': '---\ntitle: B\n---\n\n# B',
    });

    buildSiteWithResult({ contentDir, outputDir, templateDir: tplDir, incremental: true });
    const second = buildSiteWithResult({ contentDir, outputDir, templateDir: tplDir, incremental: true });
    expect(second.stats.skipped).toBe(2);

    writeContent(tplDir, {
      'default.hbs': '<h1 class="tpl">{{title}}</h1>\n{{{contentHtml}}}',
    });
    const third = buildSiteWithResult({ contentDir, outputDir, templateDir: tplDir, incremental: true });
    expect(third.stats.built).toBe(2);
    expect(third.stats.skipped).toBe(0);
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toContain('<h1 class="tpl">A</h1>');
  });

  it('removing a source file removes its output HTML and cache entry', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });

    fs.rmSync(path.join(contentDir, 'one.md'));
    const { stats, pages } = buildSiteWithResult({ contentDir, outputDir, incremental: true });

    expect(stats.total).toBe(1);
    expect(pages.map((p) => p.slug)).toEqual(['two']);
    expect(fs.existsSync(path.join(outputDir, 'one.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'two.html'))).toBe(true);
    const cache = readCache(outputDir);
    expect(cache.entries['one.md']).toBeUndefined();
    expect(cache.entries['two.md']).toBeDefined();
  });

  it('cached output is identical to a fresh clean build', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });
    buildSiteWithResult({ contentDir, outputDir, incremental: true });
    const cachedOne = fs.readFileSync(path.join(outputDir, 'one.html'), 'utf8');
    const cachedTwo = fs.readFileSync(path.join(outputDir, 'two.html'), 'utf8');

    const clean = buildSiteWithResult({ contentDir, outputDir, incremental: true, clean: true });
    expect(clean.stats.built).toBe(2);
    expect(fs.readFileSync(path.join(outputDir, 'one.html'), 'utf8')).toBe(cachedOne);
    expect(fs.readFileSync(path.join(outputDir, 'two.html'), 'utf8')).toBe(cachedTwo);
  });

  it('--clean rebuilds every page and refreshes the cache', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });
    buildSiteWithResult({ contentDir, outputDir, incremental: true });

    const { stats } = buildSiteWithResult({ contentDir, outputDir, incremental: true, clean: true });
    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(stats.timeSavedMs).toBe(0);
    expect(stats.clean).toBe(true);

    const cache = readCache(outputDir);
    expect(Object.keys(cache.entries)).toHaveLength(2);
    expect(cache.entries['one.md']?.renderedHtml.length).toBeGreaterThan(0);
  });

  it('a plain build does not write a cache manifest', () => {
    const { contentDir, outputDir } = fixture();
    buildSite({ contentDir, outputDir });
    expect(fs.existsSync(cachePath(outputDir))).toBe(false);
  });

  it('exposes build stats through buildSiteWithResult', () => {
    const { contentDir, outputDir } = fixture();
    const { stats } = buildSiteWithResult({ contentDir, outputDir, incremental: true });
    expect(stats).toEqual({
      total: 2,
      built: 2,
      skipped: 0,
      timeSavedMs: 0,
      cacheLoaded: false,
      clean: false,
    });
  });
});

describe('cache manifest', () => {
  it('stores source hashes, template hashes and rendered HTML per page', () => {
    const { contentDir, outputDir } = fixture();
    buildSiteWithResult({ contentDir, outputDir, incremental: true });

    const cache = readCache(outputDir);
    const one = cache.entries['one.md'];
    expect(one).toBeDefined();
    expect(one.slug).toBe('one');
    expect(one.sourceHash).toMatch(/^[0-9a-f]{64}$/);
    expect(one.templateHash).toMatch(/^[0-9a-f]{64}$/);
    expect(one.buildMs).toBeGreaterThanOrEqual(1);
    expect(one.renderedHtml).toContain('<title>One</title>');
    expect(one.page.contentHtml).toContain('<strong>one</strong>');
  });

  it('treats a corrupt manifest as an empty cache', () => {
    const { contentDir, outputDir } = fixture();
    writeContent(outputDir, { [CACHE_FILE_NAME]: '{not valid json' });
    const { stats } = buildSiteWithResult({ contentDir, outputDir, incremental: true });
    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
  });

  it('ignores a manifest with a mismatched version', () => {
    const { contentDir, outputDir } = fixture();
    saveBuildCache(cachePath(outputDir), {
      version: 999,
      entries: {
        'one.md': {
          slug: 'one',
          sourceHash: 'x',
          templateHash: 'y',
          page: { slug: 'one', title: 'stale', contentHtml: 'stale', content: 'stale' },
          renderedHtml: 'stale',
          buildMs: 5,
        },
      },
    });
    const { pages, stats } = buildSiteWithResult({ contentDir, outputDir, incremental: true });
    expect(stats.built).toBe(2);
    expect(pages.find((p) => p.slug === 'one')?.title).toBe('One');
  });
});

describe('CLI incremental flags', () => {
  it('parses --incremental and --clean', () => {
    const opts = parseArgs(['build', '--incremental', '--clean']);
    expect(opts.incremental).toBe(true);
    expect(opts.clean).toBe(true);
  });

  beforeAll(() => {
    ensureBuilt();
  });

  it('prints build stats and writes a cache for build --incremental', () => {
    const { contentDir, outputDir } = fixture();
    const first = spawnSync(
      process.execPath,
      [CLI_JS, 'build', '--content', contentDir, '--output', outputDir, '--incremental'],
      { cwd: REPO_ROOT, encoding: 'utf8' }
    );
    expect(first.status).toBe(0);
    expect(first.stdout).toContain('Built 2 pages');
    expect(first.stdout).toContain('Incremental build: 2 built, 0 skipped');
    expect(fs.existsSync(cachePath(outputDir))).toBe(true);

    const second = spawnSync(
      process.execPath,
      [CLI_JS, 'build', '--content', contentDir, '--output', outputDir, '--incremental'],
      { cwd: REPO_ROOT, encoding: 'utf8' }
    );
    expect(second.status).toBe(0);
    expect(second.stdout).toContain('Incremental build: 0 built, 2 skipped');
  });

  it('build --clean rebuilds every page', () => {
    const { contentDir, outputDir } = fixture();
    spawnSync(
      process.execPath,
      [CLI_JS, 'build', '--content', contentDir, '--output', outputDir, '--incremental'],
      { cwd: REPO_ROOT, encoding: 'utf8' }
    );
    const clean = spawnSync(
      process.execPath,
      [CLI_JS, 'build', '--content', contentDir, '--output', outputDir, '--clean', '--incremental'],
      { cwd: REPO_ROOT, encoding: 'utf8' }
    );
    expect(clean.status).toBe(0);
    expect(clean.stdout).toContain('Incremental build: 2 built, 0 skipped');
    expect(fs.existsSync(cachePath(outputDir))).toBe(true);
  });
});
