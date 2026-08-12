import fs from 'fs';
import os from 'os';
import path from 'path';
import { build, buildIncremental } from '../src/ssg';
import {
  CACHE_FILE,
  hashDir,
  hashFile,
  loadCache,
  saveCache,
  emptyManifest,
  cachePathFor,
} from '../src/cache';
import { Page } from '../src/types';
import { parseArgs } from '../src/cli';

function makeTempRoot(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const filePath = path.join(root, rel);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
}

function readTree(root: string): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        out[path.relative(root, full)] = fs.readFileSync(full, 'utf8');
      }
    }
  };
  walk(root);
  return out;
}

describe('cache helpers', () => {
  it('hashes a file by content', () => {
    const root = makeTempRoot('ssg-cache-');
    const file = path.join(root, 'a.md');
    const other = path.join(root, 'b.md');
    fs.writeFileSync(file, 'hello', 'utf8');
    fs.writeFileSync(other, 'world', 'utf8');
    expect(hashFile(file)).toBe(hashFile(file));
    expect(hashFile(file)).not.toBe(hashFile(other));
    fs.writeFileSync(file, 'world', 'utf8');
    expect(hashFile(file)).toBe(hashFile(other));
  });

  it('hashes a directory recursively and changes when files change', () => {
    const root = makeTempRoot('ssg-cache-');
    writeTree(root, {
      'templates/default.hbs': '<article>{{title}}</article>',
      'templates/layouts/default.hbs': '<html>{{{body}}}</html>',
    });
    const dir = path.join(root, 'templates');
    const first = hashDir(dir);
    expect(first).toBe(hashDir(dir));
    fs.writeFileSync(path.join(dir, 'default.hbs'), '<article>CHANGED</article>', 'utf8');
    expect(hashDir(dir)).not.toBe(first);
  });

  it('returns an empty hash for a missing directory', () => {
    expect(hashDir(path.join(makeTempRoot('ssg-cache-'), 'nope'))).toBe('');
  });

  it('round-trips the manifest through saveCache/loadCache', () => {
    const root = makeTempRoot('ssg-cache-');
    const cachePath = path.join(root, CACHE_FILE);
    const manifest = emptyManifest();
    manifest.entries.a = {
      source: '/tmp/a.md',
      sourceHash: 'abc',
      templateHash: 'tpl',
      page: {
        sourcePath: '/tmp/a.md',
        slug: 'a',
        title: 'A',
        date: '',
        tags: [],
        content: 'Body',
        html: '<p>Body</p>',
      },
      rendered: '<html>A</html>',
      pageMs: 12,
    };
    saveCache(cachePath, manifest);
    const loaded = loadCache(cachePath);
    expect(loaded?.version).toBe(1);
    expect(loaded?.entries.a).toEqual(manifest.entries.a);
  });

  it('ignores corrupt or incompatible manifests', () => {
    const root = makeTempRoot('ssg-cache-');
    const cachePath = path.join(root, CACHE_FILE);
    fs.writeFileSync(cachePath, 'not json{', 'utf8');
    expect(loadCache(cachePath)).toBeUndefined();
    fs.writeFileSync(cachePath, JSON.stringify({ version: 999, entries: {} }), 'utf8');
    expect(loadCache(cachePath)).toBeUndefined();
  });
});

describe('incremental build', () => {
  it('creates a cache manifest on the first build and builds every page', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    const { pages, stats } = buildIncremental({ contentDir, outputDir });

    expect(pages).toHaveLength(2);
    expect(stats.total).toBe(2);
    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(fs.existsSync(cachePathFor(outputDir))).toBe(true);

    const manifest = loadCache(cachePathFor(outputDir))!;
    expect(Object.keys(manifest.entries).sort()).toEqual(['a', 'b']);
    expect(manifest.entries.a.sourceHash).toMatch(/^[0-9a-f]{32}$/);
  });

  it('skips unchanged pages on a second build', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    buildIncremental({ contentDir, outputDir });
    const before = readTree(outputDir);

    const { stats } = buildIncremental({ contentDir, outputDir });

    expect(stats.total).toBe(2);
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(2);
    expect(readTree(outputDir)).toEqual(before);
  });

  it('rebuilds only the page whose source changed', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    buildIncremental({ contentDir, outputDir });
    const bBefore = fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8');

    fs.writeFileSync(
      path.join(contentDir, 'a.md'),
      '---\ntitle: Alpha\n---\nHello A **updated**.',
      'utf8'
    );
    const { stats } = buildIncremental({ contentDir, outputDir });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(1);
    const aHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(aHtml).toContain('<strong>updated</strong>');
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8')).toBe(bBefore);
  });

  it('rebuilds every page when a template changes', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
      'templates/default.hbs': '<article>{{title}} v1</article>',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templateDir = path.join(root, 'templates');
    const options = { contentDir, outputDir, templateDir };

    buildIncremental(options);
    expect(buildIncremental(options).stats.skipped).toBe(2);

    fs.writeFileSync(path.join(templateDir, 'default.hbs'), '<article>{{title}} v2</article>', 'utf8');
    const { stats } = buildIncremental(options);

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toContain('Alpha v2');
  });

  it('caches parsed frontmatter and rendered HTML in the manifest', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\ntags: [x]\n---\nHello A.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    buildIncremental({ contentDir, outputDir });
    const manifest = loadCache(cachePathFor(outputDir))!;
    const entry = manifest.entries.a;

    expect(entry.page.title).toBe('Alpha');
    expect(entry.page.tags).toEqual(['x']);
    expect(entry.page.content).toContain('Hello A.');
    expect(entry.rendered).toContain('<title>Alpha</title>');
  });

  it('removes output and cache entries for deleted pages', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    buildIncremental({ contentDir, outputDir });
    fs.rmSync(path.join(contentDir, 'b.md'));

    const { pages, stats } = buildIncremental({ contentDir, outputDir });

    expect(pages).toHaveLength(1);
    expect(stats.total).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    expect(loadCache(cachePathFor(outputDir))!.entries.b).toBeUndefined();
    expect(fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8')).not.toContain('Beta');
  });

  it('keeps the cached page when a newly added page is built', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    buildIncremental({ contentDir, outputDir });
    const aBefore = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');

    writeTree(root, {
      'content/c.md': '---\ntitle: Gamma\n---\nHello C.',
    });
    const { stats } = buildIncremental({ contentDir, outputDir });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(1);
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toBe(aBefore);
    expect(fs.readFileSync(path.join(outputDir, 'c.html'), 'utf8')).toContain('Gamma');
  });

  it('reports time saved when pages are skipped', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    const first = buildIncremental({ contentDir, outputDir });
    expect(first.stats.timeSaved).toBe(0);

    const second = buildIncremental({ contentDir, outputDir });
    expect(second.stats.skipped).toBe(2);
    expect(second.stats.timeSaved).toBeGreaterThanOrEqual(0);

    const manifest = loadCache(cachePathFor(outputDir))!;
    expect(second.stats.timeSaved).toBe(manifest.entries.a.pageMs + manifest.entries.b.pageMs);
  });

  it('uses the cache when only --clean is passed, but rebuilds everything', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    buildIncremental({ contentDir, outputDir });
    const { stats } = buildIncremental({ contentDir, outputDir, clean: true });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(0);
    expect(fs.existsSync(cachePathFor(outputDir))).toBe(true);
  });

  it('does a clean full build when the cache is missing', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    build({ contentDir, outputDir });
    expect(fs.existsSync(cachePathFor(outputDir))).toBe(false);

    const { stats } = buildIncremental({ contentDir, outputDir });
    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
    expect(fs.existsSync(cachePathFor(outputDir))).toBe(true);
  });

  it('keeps custom onFile plugins working for freshly built pages', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const shouter = {
      name: 'shouter',
      onFile: (page: Page) => ({ ...page, title: page.title.toUpperCase() }),
    };

    buildIncremental({ contentDir, outputDir, plugins: [shouter] });
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toContain('<title>ALPHA</title>');

    writeTree(root, {
      'content/b.md': '---\ntitle: Beta\n---\nHello B.',
    });
    buildIncremental({ contentDir, outputDir, plugins: [shouter] });

    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toContain('<title>ALPHA</title>');
    expect(fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8')).toContain('<title>BETA</title>');
  });

  it('does not delete stale output from other files when incremental', () => {
    const root = makeTempRoot('ssg-inc-');
    writeTree(root, {
      'content/a.md': '---\ntitle: Alpha\n---\nHello A.',
    });
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');

    build({ contentDir, outputDir });
    const marker = path.join(outputDir, 'keep.txt');
    fs.writeFileSync(marker, 'keep me', 'utf8');

    buildIncremental({ contentDir, outputDir });
    expect(fs.existsSync(marker)).toBe(true);
  });
});

describe('incremental CLI flags', () => {
  it('parses --incremental', () => {
    const { options } = parseArgs(['build', '--incremental']);
    expect(options.incremental).toBe(true);
  });

  it('parses --clean', () => {
    const { options } = parseArgs(['build', '--clean']);
    expect(options.clean).toBe(true);
  });

  it('parses --incremental with other flags', () => {
    const { options } = parseArgs(['build', '--incremental', '--content', 'pages', '--clean']);
    expect(options.incremental).toBe(true);
    expect(options.clean).toBe(true);
    expect(options.contentDir).toBe('pages');
  });
});
