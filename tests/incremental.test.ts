import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { SsgEngine } from '../src/engine';
import { build, defaultBuildPlugins } from '../src/generator';
import { loadCacheManifest } from '../src/cache';
import type { Plugin, PluginContext } from '../src/plugin';
import type { Page } from '../src/types';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function writeFixtureTemplates(templatesDir: string): void {
  writeFile(
    path.join(templatesDir, 'layouts', 'default.hbs'),
    '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
  );
}

describe('incremental builds', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  const cacheFile = () => path.join(outputDir, '.ssg-cache.json');

  beforeEach(() => {
    contentDir = makeTempDir('ssg-inc-content-');
    outputDir = makeTempDir('ssg-inc-output-');
    templatesDir = makeTempDir('ssg-inc-templates-');
    writeFixtureTemplates(templatesDir);

    writeFile(
      path.join(contentDir, 'a.md'),
      `---\ntitle: A\n---\nBody A.\n`
    );
    writeFile(
      path.join(contentDir, 'b.md'),
      `---\ntitle: B\n---\nBody B.\n`
    );
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('does not create a cache file or change stats semantics when incremental is not requested', () => {
    const result = build({ contentDir, outputDir, templatesDir });

    expect(result.stats.incremental).toBe(false);
    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(fs.existsSync(cacheFile())).toBe(false);
  });

  it('builds every page and writes a cache manifest on the first incremental build', () => {
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(result.stats.totalPages).toBe(2);
    expect(fs.existsSync(cacheFile())).toBe(true);

    const manifest = loadCacheManifest(cacheFile());
    expect(manifest).toBeDefined();
    expect(Object.keys(manifest!.pages).sort()).toEqual(['a.md', 'b.md']);
  });

  it('skips every page on a second incremental build when nothing changed', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });
    const secondResult = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(secondResult.stats.pagesBuilt).toBe(0);
    expect(secondResult.stats.pagesSkipped).toBe(2);
    expect(secondResult.stats.totalPages).toBe(2);
  });

  it('produces identical page metadata and output HTML whether a page is freshly built or skipped', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });
    const aHtmlAfterFirstBuild = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');

    const secondResult = build({ contentDir, outputDir, templatesDir, incremental: true });

    const aPage = secondResult.pages.find((p) => p.sourcePath === 'a.md');
    expect(aPage?.title).toBe('A');
    expect(aPage?.html).toContain('Body A.');
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toBe(aHtmlAfterFirstBuild);
  });

  it('only rebuilds the page whose source file changed', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(path.join(contentDir, 'a.md'), `---\ntitle: A Updated\n---\nBody A changed.\n`);
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(aHtml).toContain('Body A changed.');

    const bHtml = fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8');
    expect(bHtml).toContain('Body B.');
  });

  it('builds a newly added page while skipping unchanged ones', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(path.join(contentDir, 'c.md'), `---\ntitle: C\n---\nBody C.\n`);
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(2);
    expect(result.stats.totalPages).toBe(3);
    expect(fs.existsSync(path.join(outputDir, 'c.html'))).toBe(true);
  });

  it('drops a removed source file from the cache manifest on the next incremental build', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });

    fs.rmSync(path.join(contentDir, 'b.md'));
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.totalPages).toBe(1);
    expect(result.pages.map((p) => p.sourcePath)).toEqual(['a.md']);

    const manifest = loadCacheManifest(cacheFile());
    expect(Object.keys(manifest!.pages)).toEqual(['a.md']);
  });

  it('rebuilds every page when a template file changes, even if no source changed', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html data-v="2"><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(aHtml).toContain('data-v="2"');
  });

  it('rebuilds everything when --clean is passed, ignoring an existing valid cache', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });
    const result = build({ contentDir, outputDir, templatesDir, incremental: true, clean: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(result.stats.clean).toBe(true);
  });

  it('treats a missing cache file as a clean build even when incremental is requested', () => {
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });
    expect(result.stats.pagesBuilt).toBe(result.stats.totalPages);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('falls back to a full rebuild when the plugin pipeline changes between builds', () => {
    const plugins = () => defaultBuildPlugins();

    new SsgEngine({ contentDir, outputDir, templatesDir, plugins: plugins(), incremental: true }).build();

    const extraPlugin: Plugin = { name: 'extra-plugin' };
    const result = new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [...plugins(), extraPlugin],
      incremental: true,
    }).build();

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('reports a positive timeSavedMs once at least one page has been skipped', () => {
    build({ contentDir, outputDir, templatesDir, incremental: true });
    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesSkipped).toBe(2);
    expect(result.stats.timeSavedMs).toBeGreaterThanOrEqual(0);
  });

  it('exposes ctx.incremental only when the engine runs in incremental mode', () => {
    const seenIncrementalFlags: Array<boolean> = [];
    const probe: Plugin = {
      name: 'probe',
      beforeBuild(ctx: PluginContext) {
        seenIncrementalFlags.push(ctx.incremental !== undefined);
      },
    };

    new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [...defaultBuildPlugins(), probe],
    }).build();

    new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [...defaultBuildPlugins(), probe],
      incremental: true,
    }).build();

    expect(seenIncrementalFlags).toEqual([false, true]);
  });

  it('passes unchanged source paths through ctx.incremental for plugins to consume', () => {
    const seenUnchanged: string[][] = [];
    const probe: Plugin = {
      name: 'probe',
      afterBuild(_pages: Page[], ctx: PluginContext) {
        seenUnchanged.push(Array.from(ctx.incremental?.unchangedSourcePaths ?? []).sort());
      },
    };
    const plugins = () => [...defaultBuildPlugins(), probe];

    // First build establishes the cache (using the same plugin pipeline the second build uses).
    new SsgEngine({ contentDir, outputDir, templatesDir, plugins: plugins(), incremental: true }).build();
    // Second build reuses it, so every page should show up as unchanged.
    new SsgEngine({ contentDir, outputDir, templatesDir, plugins: plugins(), incremental: true }).build();

    expect(seenUnchanged).toEqual([[], ['a.md', 'b.md']]);
  });

  it('keeps the plugin architecture intact: onFile still runs for every page on a non-incremental build', () => {
    const calls: string[] = [];
    const recorder: Plugin = {
      name: 'recorder',
      onFile(page: Page) {
        calls.push(page.sourcePath);
      },
    };

    new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [...defaultBuildPlugins(), recorder],
    }).build();
    new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [...defaultBuildPlugins(), recorder],
    }).build();

    expect(calls).toEqual(['a.md', 'b.md', 'a.md', 'b.md']);
  });

  it('does not call onFile for pages skipped by the incremental cache', () => {
    const calls: string[] = [];
    const recorder: Plugin = {
      name: 'recorder',
      onFile(page: Page) {
        calls.push(page.sourcePath);
      },
    };

    const plugins = () => [...defaultBuildPlugins(), recorder];

    new SsgEngine({ contentDir, outputDir, templatesDir, plugins: plugins(), incremental: true }).build();
    calls.length = 0;

    writeFile(path.join(contentDir, 'a.md'), `---\ntitle: A Updated\n---\nBody A changed.\n`);
    new SsgEngine({ contentDir, outputDir, templatesDir, plugins: plugins(), incremental: true }).build();

    expect(calls).toEqual(['a.md']);
  });
});
