import fs from 'fs';
import os from 'os';
import path from 'path';
import { SSG } from './engine';
import { buildSite, buildSiteWithStats } from './build';
import { builtinPlugins } from './plugins';
import { Plugin } from './plugin';
import { parseArgs } from './cli';

const PAGE_A = '---\ntitle: A\n---\n\nPage A.';
const PAGE_B = '---\ntitle: B\n---\n\nPage B.';

function makePluginEngine(contentDir: string, outputDir: string, ...extra: Plugin[]): SSG {
  const engine = new SSG({
    options: { contentDir, outputDir },
    plugins: [...builtinPlugins(), ...extra],
  });
  engine.start();
  return engine;
}

describe('incremental builds', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  function write(name: string, content: string): string {
    const p = path.join(contentDir, name);
    fs.writeFileSync(p, content, 'utf-8');
    return p;
  }

  it('writes a .ssg-cache.json manifest after a build', () => {
    write('a.md', PAGE_A);
    buildSite({ contentDir, outputDir });
    const manifestPath = path.join(outputDir, '.ssg-cache.json');
    expect(fs.existsSync(manifestPath)).toBe(true);
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.version).toBe(1);
    expect(manifest.pages.a).toBeDefined();
  });

  it('skips every unchanged page on an incremental rebuild', () => {
    write('a.md', PAGE_A);
    write('b.md', PAGE_B);
    buildSite({ contentDir, outputDir });

    const { stats } = buildSiteWithStats({ contentDir, outputDir }, { incremental: true });

    expect(stats.total).toBe(2);
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(2);
    expect(stats.usedCache).toBe(true);
    expect(stats.timeSavedMs).toBeGreaterThanOrEqual(0);
  });

  it('keeps output files intact for skipped pages', () => {
    write('a.md', PAGE_A);
    buildSite({ contentDir, outputDir });

    buildSiteWithStats({ contentDir, outputDir }, { incremental: true });

    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8')).toContain('Page A');
  });

  it('rebuilds only the changed page when one source file changes', () => {
    write('a.md', PAGE_A);
    write('b.md', PAGE_B);
    buildSite({ contentDir, outputDir });

    write('a.md', '---\ntitle: A2\n---\n\nChanged body.');
    const { stats, pages } = buildSiteWithStats({ contentDir, outputDir }, { incremental: true });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(1);
    const a = pages.find((p) => p.slug === 'a');
    expect(a && a.data.title).toBe('A2');
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8')).toContain('Changed body');
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf-8')).toContain('Page B');
  });

  it('rebuilds every page when a template changes', () => {
    const templatesDir = path.join(root, 'templates');
    fs.mkdirSync(templatesDir);
    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), 'ONE:{{{html}}}', 'utf-8');
    write('a.md', PAGE_A);
    write('b.md', PAGE_B);
    buildSite({ contentDir, outputDir, templatesDir });
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8')).toContain('ONE:');

    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), 'TWO:{{{html}}}', 'utf-8');
    const { stats } = buildSiteWithStats(
      { contentDir, outputDir, templatesDir },
      { incremental: true }
    );

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8')).toContain('TWO:');
  });

  it('rebuilds when a partial used by every page changes', () => {
    const templatesDir = path.join(root, 'templates');
    fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
    fs.mkdirSync(path.join(templatesDir, 'partials'), { recursive: true });
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'base.hbs'),
      'BODY:{{{body}}}',
      'utf-8'
    );
    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), '{{> header}}{{{html}}}', 'utf-8');
    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), 'H1', 'utf-8');
    write('a.md', PAGE_A);
    buildSite({ contentDir, outputDir, templatesDir });

    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), 'H2', 'utf-8');
    const { stats } = buildSiteWithStats(
      { contentDir, outputDir, templatesDir },
      { incremental: true }
    );

    expect(stats.built).toBe(1);
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8')).toContain('H2');
  });

  it('removes the output file for a deleted content file', () => {
    write('a.md', PAGE_A);
    write('b.md', PAGE_B);
    buildSite({ contentDir, outputDir });

    fs.rmSync(path.join(contentDir, 'b.md'));
    const { stats } = buildSiteWithStats({ contentDir, outputDir }, { incremental: true });

    expect(stats.total).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(false);
  });

  it('treats a missing cache manifest as a clean build', () => {
    write('a.md', PAGE_A);
    buildSite({ contentDir, outputDir });

    fs.rmSync(path.join(outputDir, '.ssg-cache.json'));
    fs.writeFileSync(path.join(outputDir, 'stale.html'), 'stale', 'utf-8');
    const { stats } = buildSiteWithStats({ contentDir, outputDir }, { incremental: true });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(0);
    expect(fs.existsSync(path.join(outputDir, 'stale.html'))).toBe(false);
  });

  it('forces a full rebuild when --clean is passed with --incremental', () => {
    write('a.md', PAGE_A);
    write('b.md', PAGE_B);
    buildSite({ contentDir, outputDir });

    const { stats } = buildSiteWithStats(
      { contentDir, outputDir },
      { incremental: true, clean: true }
    );

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(stats.usedCache).toBe(false);
  });

  it('caches parsed frontmatter data in the manifest', () => {
    write(
      'a.md',
      '---\ntitle: A\ndate: 2024-05-05\ntags:\n  - x\n  - y\n---\n\nbody'
    );
    buildSite({ contentDir, outputDir });

    const manifest = JSON.parse(
      fs.readFileSync(path.join(outputDir, '.ssg-cache.json'), 'utf-8')
    );
    expect(manifest.pages.a.page.data).toEqual({
      title: 'A',
      date: '2024-05-05',
      tags: ['x', 'y'],
    });
  });

  it('reuses plugin-transformed output for unchanged pages', () => {
    const stamp: Plugin = {
      name: 'stamp',
      onFile(page) {
        return { ...page, data: { ...page.data, title: `${page.data.title ?? ''}!` } };
      },
    };
    write('a.md', PAGE_A);

    const first = makePluginEngine(contentDir, outputDir, stamp);
    const firstPages = first.build();
    expect(firstPages[0].data.title).toBe('A!');

    const second = makePluginEngine(contentDir, outputDir, stamp);
    const pages = second.build({ incremental: true });

    expect(second.lastBuildStats && second.lastBuildStats.skipped).toBe(1);
    expect(second.lastBuildStats && second.lastBuildStats.built).toBe(0);
    expect(pages[0].data.title).toBe('A!');
  });

  it('reports the number of built and skipped pages', () => {
    write('a.md', PAGE_A);
    write('b.md', PAGE_B);
    buildSite({ contentDir, outputDir });

    const { stats } = buildSiteWithStats({ contentDir, outputDir }, { incremental: true });
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(2);
  });

  it('reports time saved from the cached render durations', () => {
    write('a.md', PAGE_A);
    buildSite({ contentDir, outputDir });
    const manifestPath = path.join(outputDir, '.ssg-cache.json');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    manifest.pages.a.renderMs = 42;
    fs.writeFileSync(manifestPath, JSON.stringify(manifest), 'utf-8');

    const { stats } = buildSiteWithStats({ contentDir, outputDir }, { incremental: true });
    expect(stats.timeSavedMs).toBe(42);
  });
});

describe('parseArgs incremental flags', () => {
  it('parses --incremental and --clean flags', () => {
    const args = parseArgs(['build', '--incremental']);
    expect(args.incremental).toBe(true);
    expect(args.clean).toBe(false);

    const clean = parseArgs(['build', '--clean']);
    expect(clean.clean).toBe(true);
    expect(clean.incremental).toBe(false);

    const both = parseArgs(['build', '--incremental', '--clean']);
    expect(both.incremental).toBe(true);
    expect(both.clean).toBe(true);
  });

  it('defaults the flags to false', () => {
    const args = parseArgs(['build']);
    expect(args.incremental).toBe(false);
    expect(args.clean).toBe(false);
  });
});
