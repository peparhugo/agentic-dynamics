import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/build';
import { parseArgs } from '../src/cli';
import { CACHE_FILE_NAME, loadManifest } from '../src/cache';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function createContent(contentDir: string): void {
  writeFile(
    path.join(contentDir, 'first.md'),
    `---
title: First
date: 2024-02-01
---
# First

Hello first.
`
  );
  writeFile(
    path.join(contentDir, 'second.md'),
    `---
title: Second
date: 2024-01-01
---
# Second

Hello second.
`
  );
}

describe('parseArgs incremental flags', () => {
  it('parses --incremental', () => {
    expect(parseArgs(['node', 'ssg', 'build', '--incremental']).incremental).toBe(true);
  });

  it('parses --clean', () => {
    expect(parseArgs(['node', 'ssg', 'build', '--clean']).clean).toBe(true);
  });

  it('defaults both flags to false', () => {
    const args = parseArgs(['node', 'ssg', 'build']);
    expect(args.incremental).toBe(false);
    expect(args.clean).toBe(false);
  });
});

describe('incremental build', () => {
  it('writes a cache manifest and builds all pages on the first run', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    const result = build({ contentDir, outputDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const cachePath = path.join(outputDir, CACHE_FILE_NAME);
    expect(fs.existsSync(cachePath)).toBe(true);
    const manifest = loadManifest(cachePath);
    expect(Object.keys(manifest.pages)).toHaveLength(2);
    expect(Object.keys(manifest.files)).toHaveLength(2);
  });

  it('skips all pages when nothing changed', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });
    const second = build({ contentDir, outputDir, incremental: true });

    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    // Only the index is rewritten on an unchanged build.
    expect(second.writtenFiles).toEqual([path.join(outputDir, 'index.html')]);
  });

  it('does not rewrite skipped page files', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });

    const pagePath = path.join(outputDir, 'first.html');
    const marker = '\n<!-- MARKER -->\n';
    fs.appendFileSync(pagePath, marker);

    build({ contentDir, outputDir, incremental: true });

    const content = fs.readFileSync(pagePath, 'utf8');
    expect(content).toContain('MARKER');
  });

  it('rebuilds only the changed source file', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });

    writeFile(
      path.join(contentDir, 'first.md'),
      `---
title: First Updated
date: 2024-02-01
---
# First

Changed body.
`
    );

    const result = build({ contentDir, outputDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    const firstHtml = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf8');
    expect(firstHtml).toContain('First Updated');
    expect(firstHtml).toContain('Changed body.');
  });

  it('rebuilds all pages when a template changes', () => {
    const contentDir = makeTempDir();
    const templatesDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);
    writeFile(path.join(templatesDir, 'page.hbs'), '<div class="v1">{{title}}</div>{{{content}}}');

    build({ contentDir, outputDir, templatesDir, incremental: true });

    writeFile(path.join(templatesDir, 'page.hbs'), '<div class="v2">{{title}}</div>{{{content}}}');

    const result = build({ contentDir, outputDir, templatesDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const firstHtml = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf8');
    expect(firstHtml).toContain('v2');
  });

  it('performs a full rebuild when clean is passed', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });
    const result = build({ contentDir, outputDir, incremental: true, clean: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('falls back to a full build when the cache is missing', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    // Full build first (writes the manifest), then delete it to simulate a missing cache.
    build({ contentDir, outputDir });
    fs.unlinkSync(path.join(outputDir, CACHE_FILE_NAME));

    const result = build({ contentDir, outputDir, incremental: true });
    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('non-incremental build always rebuilds everything', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir });
    const result = build({ contentDir, outputDir });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(result.writtenFiles).toHaveLength(3);
  });

  it('removes stale output and cache entries for deleted sources', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);

    fs.unlinkSync(path.join(contentDir, 'second.md'));

    const result = build({ contentDir, outputDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(0);
    expect(result.stats.pagesSkipped).toBe(1);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(false);

    const manifest = loadManifest(path.join(outputDir, CACHE_FILE_NAME));
    expect(Object.keys(manifest.pages)).toEqual(['first']);
  });

  it('builds only the newly added page', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });

    writeFile(
      path.join(contentDir, 'third.md'),
      `---
title: Third
date: 2024-03-01
---
# Third
`
    );

    const result = build({ contentDir, outputDir, incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(2);
    expect(fs.existsSync(path.join(outputDir, 'third.html'))).toBe(true);
  });

  it('reports time saved when pages are skipped', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    createContent(contentDir);

    build({ contentDir, outputDir, incremental: true });
    const result = build({ contentDir, outputDir, incremental: true });

    expect(result.stats.pagesSkipped).toBe(2);
    expect(result.stats.timeSavedMs).toBeGreaterThanOrEqual(0);
  });
});
