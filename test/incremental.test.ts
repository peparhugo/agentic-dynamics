import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from '../src/build';
import { parseArgs, runCli } from '../src/cli';
import { CACHE_FILE, hashContent } from '../src/cache';
import type { BuildCache, BuildStats } from '../src/cache';

const PAGE_A = `---
title: Page A
date: 2024-01-01
---
# Page A

Alpha content.
`;

const PAGE_B = `---
title: Page B
date: 2024-02-01
---
# Page B

Beta content.
`;

const TEMPLATE_V1 = `<html><head><title>{{title}}</title></head><body class="v1">{{{body}}}</body></html>`;
const TEMPLATE_V2 = `<html><head><title>{{title}}</title></head><body class="v2">{{{body}}}</body></html>`;

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incr-'));
}

function writeFiles(root: string, files: Record<string, string>): void {
  fs.mkdirSync(root, { recursive: true });
  for (const [name, contents] of Object.entries(files)) {
    const file = path.join(root, name);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, contents, 'utf-8');
  }
}

function read(dir: string, file: string): string {
  return fs.readFileSync(path.join(dir, file), 'utf-8');
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

function cachePathFor(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE);
}

function readCache(outputDir: string): BuildCache {
  return JSON.parse(read(outputDir, CACHE_FILE)) as BuildCache;
}

function statsOf(result: { stats: BuildStats }): BuildStats {
  return result.stats;
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
  });

  afterEach(() => {
    cleanup(root);
  });

  it('builds every page on the first incremental run and writes a cache manifest', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });

    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).incremental).toBe(true);
    expect(statsOf(result).builtPages).toBe(2);
    expect(statsOf(result).skippedPages).toBe(0);
    expect(fs.existsSync(cachePathFor(outputDir))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(true);

    const cache = readCache(outputDir);
    expect(cache.entries['a.md'].sourceHash).toBe(hashContent(PAGE_A));
    expect(cache.entries['a.md'].data.title).toBe('Page A');
    expect(cache.entries['a.md'].outputHtml).toContain('Alpha content.');
    expect(cache.entries['a.md'].html).toContain('<h1>Page A</h1>');
  });

  it('skips every page when nothing changed', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    const before = fs.statSync(path.join(outputDir, 'a.html')).mtimeMs;
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(0);
    expect(statsOf(result).skippedPages).toBe(2);
    expect(statsOf(result).cached).toBe(true);
    expect(statsOf(result).timeSavedMs).toBeGreaterThan(0);
    expect(fs.statSync(path.join(outputDir, 'a.html')).mtimeMs).toBe(before);
    expect(read(outputDir, 'a.html')).toContain('Alpha content.');
    expect(read(outputDir, 'b.html')).toContain('Beta content.');
  });

  it('rebuilds only the page whose source changed', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    const updated = PAGE_B.replace('Beta content.', 'Beta updated.');
    writeFiles(contentDir, { 'b.md': updated });

    const beforeA = fs.statSync(path.join(outputDir, 'a.html')).mtimeMs;
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(1);
    expect(statsOf(result).skippedPages).toBe(1);

    expect(read(outputDir, 'b.html')).toContain('Beta updated.');
    expect(read(outputDir, 'b.html')).not.toContain('Beta content.');
    expect(fs.statSync(path.join(outputDir, 'a.html')).mtimeMs).toBe(beforeA);
    expect(read(outputDir, 'a.html')).toContain('Alpha content.');
  });

  it('builds only newly added pages on subsequent runs', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    writeFiles(contentDir, { 'b.md': PAGE_B });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(1);
    expect(statsOf(result).skippedPages).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(true);
  });

  it('invalidates every page when a template file changes', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    writeFiles(templatesDir, { 'default.hbs': TEMPLATE_V1 });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(read(outputDir, 'a.html')).toContain('class="v1"');

    writeFiles(templatesDir, { 'default.hbs': TEMPLATE_V2 });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(2);
    expect(statsOf(result).skippedPages).toBe(0);
    expect(read(outputDir, 'a.html')).toContain('class="v2"');
    expect(read(outputDir, 'a.html')).not.toContain('class="v1"');
  });

  it('invalidates pages when a layout or partial file changes', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A });
    writeFiles(templatesDir, {
      'default.hbs': '<main>{{> tag}}</main>',
      'partials/tag.hbs': '<span class="old">x</span>',
    });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });
    expect(read(outputDir, 'a.html')).toContain('class="old"');

    writeFiles(templatesDir, { 'partials/tag.hbs': '<span class="new">x</span>' });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(1);
    expect(read(outputDir, 'a.html')).toContain('class="new"');
  });

  it('treats a missing cache as a clean build', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    fs.rmSync(cachePathFor(outputDir), { force: true });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(2);
    expect(statsOf(result).skippedPages).toBe(0);
    expect(statsOf(result).cached).toBe(false);
    expect(fs.existsSync(cachePathFor(outputDir))).toBe(true);
  });

  it('respects a corrupted cache manifest by rebuilding everything', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    fs.writeFileSync(cachePathFor(outputDir), '{ not valid json', 'utf-8');
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(1);
    expect(read(outputDir, 'a.html')).toContain('Alpha content.');
  });

  it('--clean forces a full rebuild even when the cache is fresh', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    const result = buildSite(contentDir, outputDir, templatesDir, {
      incremental: true,
      clean: true,
    });

    expect(statsOf(result).incremental).toBe(false);
    expect(statsOf(result).builtPages).toBe(2);
    expect(statsOf(result).skippedPages).toBe(0);
  });

  it('non-incremental builds always rebuild every page', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    const result = buildSite(contentDir, outputDir, templatesDir);

    expect(statsOf(result).incremental).toBe(false);
    expect(statsOf(result).builtPages).toBe(2);
    expect(statsOf(result).skippedPages).toBe(0);
  });

  it('uses cached frontmatter so the index and site context stay correct', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    const updatedA = PAGE_A.replace('title: Page A', 'title: Alpha Renamed').replace(
      'Alpha content.',
      'Alpha changed.',
    );
    writeFiles(contentDir, { 'a.md': updatedA });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(1);

    const index = read(outputDir, 'index.html');
    expect(index).toContain('Alpha Renamed');
    expect(index).toContain('Page B');

    const cache = readCache(outputDir);
    expect(cache.entries['b.md'].data.title).toBe('Page B');
    expect(cache.entries['b.md'].outputHtml).toContain('Beta content.');
  });

  it('prunes entries for removed pages from the cache manifest', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A, 'b.md': PAGE_B });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    fs.rmSync(path.join(contentDir, 'b.md'), { force: true });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).builtPages).toBe(0);
    expect(statsOf(result).skippedPages).toBe(1);
    expect(Object.keys(readCache(outputDir).entries).sort()).toEqual(['a.md']);
  });

  it('re-writes an output file that was deleted even when the page is cached', () => {
    writeFiles(contentDir, { 'a.md': PAGE_A });
    buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    fs.rmSync(path.join(outputDir, 'a.html'), { force: true });
    const result = buildSite(contentDir, outputDir, templatesDir, { incremental: true });

    expect(statsOf(result).skippedPages).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(read(outputDir, 'a.html')).toContain('Alpha content.');
  });
});

describe('incremental build options via buildSite and CLI', () => {
  let root: string;

  beforeEach(() => {
    root = makeTempDir();
  });

  afterEach(() => {
    cleanup(root);
  });

  it('propagates the incremental flag through buildSite options', () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFiles(contentDir, { 'a.md': PAGE_A });

    const result = buildSite(contentDir, outputDir, 'templates', { incremental: true });

    expect(result.stats.incremental).toBe(true);
    expect(result.stats.totalPages).toBe(1);
    expect(fs.existsSync(path.join(outputDir, CACHE_FILE))).toBe(true);
  });

  it('parseArgs recognises --incremental and --clean flags', () => {
    expect(parseArgs(['build']).incremental).toBe(false);
    expect(parseArgs(['build']).clean).toBe(false);
    expect(parseArgs(['build', '--incremental']).incremental).toBe(true);
    expect(parseArgs(['build', '--clean']).clean).toBe(true);
    expect(parseArgs(['build', '--incremental', '--clean']).incremental).toBe(true);
    expect(parseArgs(['build', '--incremental', '--clean']).clean).toBe(true);
  });

  it('runCli prints incremental build stats', () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFiles(contentDir, { 'a.md': PAGE_A });

    const writeSpy = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    let output = '';
    try {
      runCli(['build', '--content', contentDir, '--output', outputDir, '--incremental']);
      runCli(['build', '--content', contentDir, '--output', outputDir, '--incremental']);
      output = writeSpy.mock.calls.map((c) => String(c[0])).join('');
    } finally {
      writeSpy.mockRestore();
    }

    expect(output).toContain('Incremental build: 0 built, 1 skipped');
    expect(output).toContain('ms saved');
  });

  it('runCli respects --clean to force a full build', () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFiles(contentDir, { 'a.md': PAGE_A });

    runCli(['build', '--content', contentDir, '--output', outputDir, '--incremental']);

    const writeSpy = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    let output = '';
    try {
      runCli(['build', '--content', contentDir, '--output', outputDir, '--incremental', '--clean']);
      output = writeSpy.mock.calls.map((c) => String(c[0])).join('');
    } finally {
      writeSpy.mockRestore();
    }

    expect(output).toContain('Incremental build: 1 built, 0 skipped');
  });
});
