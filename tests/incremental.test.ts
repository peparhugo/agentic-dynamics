import { mkdtempSync, writeFileSync, mkdirSync, readFileSync, existsSync, rmSync, utimesSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';
import { CACHE_FILE, hashString } from '../src/cache';

function makeTempDir(): string {
  return mkdtempSync(path.join(tmpdir(), 'ssg-inc-test-'));
}

function writeFixture(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, content, 'utf8');
  }
}

function fixture(): { dir: string; content: string; dist: string } {
  const dir = makeTempDir();
  const content = path.join(dir, 'content');
  const dist = path.join(dir, 'dist');
  writeFixture(dir, {
    'content/one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n# One\n',
    'content/two.md': '---\ntitle: Two\ndate: 2024-01-02\n---\n# Two\n',
  });
  return { dir, content, dist };
}

const cachePath = (dir: string): string => path.join(dir, CACHE_FILE);

describe('incremental builds', () => {
  it('writes a cache manifest on every build', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist);
    expect(existsSync(cachePath(dist))).toBe(true);
  });

  it('skips every page on a second build with no changes', async () => {
    const { content, dist } = fixture();
    const first = await buildSite(content, dist, { incremental: true });
    expect(first.stats).toMatchObject({ built: 2, skipped: 0, total: 2, incremental: true });

    const oneBefore = readFileSync(path.join(dist, 'one.html'), 'utf8');

    const second = await buildSite(content, dist, { incremental: true });
    expect(second.stats).toMatchObject({ built: 0, skipped: 2, total: 2, incremental: true });
    expect(second.stats!.timeSaved).toBeGreaterThan(0);

    expect(readFileSync(path.join(dist, 'one.html'), 'utf8')).toBe(oneBefore);
    expect(second.files).toHaveLength(3);
  });

  it('reuses cached frontmatter for skipped pages', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });

    const second = await buildSite(content, dist, { incremental: true });
    expect(second.stats!.skipped).toBe(2);

    const bySlug = new Map(second.pages.map((page) => [page.slug, page]));
    expect(bySlug.get('one')?.title).toBe('One');
    expect(bySlug.get('one')?.date).toBe('2024-01-01');
    expect(bySlug.get('two')?.title).toBe('Two');

    const manifest = JSON.parse(readFileSync(cachePath(dist), 'utf8'));
    expect(manifest.entries['one.md'].title).toBe('One');
    expect(manifest.entries['one.md'].date).toBe('2024-01-01');
    expect(manifest.entries['one.md'].html).toContain('<h1>One</h1>');
  });

  it('rebuilds only the changed page when a single source changes', async () => {
    const { dir, content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });

    const oneBefore = readFileSync(path.join(dist, 'one.html'), 'utf8');
    writeFileSync(path.join(dir, 'content/two.md'), '---\ntitle: Two\ndate: 2024-01-02\n---\n# Two Edited\n', 'utf8');

    const result = await buildSite(content, dist, { incremental: true });
    expect(result.stats).toMatchObject({ built: 1, skipped: 1 });

    expect(readFileSync(path.join(dist, 'one.html'), 'utf8')).toBe(oneBefore);
    expect(readFileSync(path.join(dist, 'two.html'), 'utf8')).toContain('<h1>Two Edited</h1>');
  });

  it('does not rebuild pages whose source hash is unchanged', async () => {
    const { dir, content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });

    const manifestBefore = JSON.parse(readFileSync(cachePath(dist), 'utf8'));
    expect(manifestBefore.entries['one.md'].sourceHash).toBe(hashString('---\ntitle: One\ndate: 2024-01-01\n---\n# One\n'));

    const touch = path.join(dir, 'content/one.md');
    const now = new Date(Date.now() + 60_000);
    utimesSync(touch, now, now);

    const result = await buildSite(content, dist, { incremental: true });
    expect(result.stats).toMatchObject({ built: 0, skipped: 2 });
  });

  it('invalidates all entries when a template changes', async () => {
    const dir = makeTempDir();
    const content = path.join(dir, 'content');
    const dist = path.join(dir, 'dist');
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\n# One\n',
      'templates/default.hbs': '<main>{{{body}}}</main>',
    });

    await buildSite(content, dist, { templatesDir: path.join(dir, 'templates'), incremental: true });
    expect(readFileSync(path.join(dist, 'one.html'), 'utf8')).toContain('<main><h1>One</h1>');

    writeFileSync(path.join(dir, 'templates/default.hbs'), '<main class="v2">{{{body}}}</main>', 'utf8');

    const result = await buildSite(content, dist, { templatesDir: path.join(dir, 'templates'), incremental: true });
    expect(result.stats).toMatchObject({ built: 1, skipped: 0 });
    expect(readFileSync(path.join(dist, 'one.html'), 'utf8')).toContain('<main class="v2"><h1>One</h1>');
  });

  it('invalidates all entries when a partial changes', async () => {
    const dir = makeTempDir();
    const content = path.join(dir, 'content');
    const dist = path.join(dir, 'dist');
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\nBody',
      'templates/default.hbs': '{{> head}}<p>{{title}}</p>',
      'templates/partials/head.hbs': '<title>v1</title>',
    });

    await buildSite(content, dist, { templatesDir: path.join(dir, 'templates'), incremental: true });
    expect(readFileSync(path.join(dist, 'one.html'), 'utf8')).toContain('<title>v1</title>');

    writeFileSync(path.join(dir, 'templates/partials/head.hbs'), '<title>v2</title>', 'utf8');

    const result = await buildSite(content, dist, { templatesDir: path.join(dir, 'templates'), incremental: true });
    expect(result.stats).toMatchObject({ built: 1, skipped: 0 });
    expect(readFileSync(path.join(dist, 'one.html'), 'utf8')).toContain('<title>v2</title>');
  });

  it('does a clean build when the cache is missing', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });
    rmSync(cachePath(dist), { force: true });

    const result = await buildSite(content, dist, { incremental: true });
    expect(result.stats).toMatchObject({ built: 2, skipped: 0 });
    expect(existsSync(cachePath(dist))).toBe(true);
  });

  it('does a clean build when --clean is passed', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });

    const result = await buildSite(content, dist, { incremental: true, clean: true });
    expect(result.stats).toMatchObject({ built: 2, skipped: 0 });
  });

  it('does a clean build when the template hash changes even with cache present', async () => {
    const dir = makeTempDir();
    const content = path.join(dir, 'content');
    const dist = path.join(dir, 'dist');
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\nBody',
      'templates/default.hbs': '<main>{{{body}}}</main>',
    });

    await buildSite(content, dist, { templatesDir: path.join(dir, 'templates'), incremental: true });
    writeFileSync(path.join(dir, 'templates/default.hbs'), '<main>NEW{{{body}}}</main>', 'utf8');

    const result = await buildSite(content, dist, { templatesDir: path.join(dir, 'templates'), incremental: true });
    expect(result.stats!.built).toBe(1);
    expect(result.stats!.skipped).toBe(0);
  });

  it('reports accurate build stats', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });

    const result = await buildSite(content, dist, { incremental: true });
    const stats = result.stats!;
    expect(stats.total).toBe(2);
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(2);
    expect(stats.timeSaved).toBeGreaterThan(0);
    expect(stats.time).toBeGreaterThanOrEqual(0);
    expect(stats.incremental).toBe(true);
  });

  it('keeps the cache file out of the emitted files list', async () => {
    const { content, dist } = fixture();
    const result = await buildSite(content, dist, { incremental: true });
    expect(result.files.some((file) => file.endsWith(CACHE_FILE))).toBe(false);
  });

  it('non-incremental builds still build every page and refresh the cache', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });
    const result = await buildSite(content, dist);
    expect(result.stats).toMatchObject({ built: 2, skipped: 0, total: 2, incremental: false });

    const next = await buildSite(content, dist, { incremental: true });
    expect(next.stats).toMatchObject({ built: 0, skipped: 2 });
  });

  it('regenerates the index page from cached metadata', async () => {
    const { content, dist } = fixture();
    await buildSite(content, dist, { incremental: true });

    const result = await buildSite(content, dist, { incremental: true });
    expect(result.stats!.skipped).toBe(2);

    const index = readFileSync(path.join(dist, 'index.html'), 'utf8');
    expect(index).toContain('href="one.html"');
    expect(index).toContain('href="two.html"');
    expect(index).toContain('>One</a>');
    expect(index).toContain('>Two</a>');
  });
});
