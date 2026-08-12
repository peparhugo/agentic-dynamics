import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';

import { build, DEFAULT_CACHE_FILE, loadManifest } from '../src/ssg';
import { parseArgs } from '../src/cli';
import type { BuildStats } from '../src/types';

let tempRoot: string;
let contentDir: string;
let templateDir: string;
let outputDir: string;
let cacheFile: string;

const FIXTURES = path.join(__dirname, 'fixtures');
const TEMPLATES = path.join(FIXTURES, 'templates');

function writeSource(name: string, body: string): Promise<void> {
  const file = path.join(contentDir, name);
  return fs.mkdir(path.dirname(file), { recursive: true }).then(() =>
    fs.writeFile(file, body, 'utf8')
  );
}

async function readOutput(name: string): Promise<string> {
  return fs.readFile(path.join(outputDir, name), 'utf8');
}

beforeEach(async () => {
  tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incremental-test-'));
  contentDir = path.join(tempRoot, 'content');
  templateDir = path.join(tempRoot, 'templates');
  outputDir = path.join(tempRoot, 'dist');
  cacheFile = path.join(outputDir, DEFAULT_CACHE_FILE);
  await fs.mkdir(contentDir, { recursive: true });
  await fs.mkdir(templateDir, { recursive: true });
});

afterEach(async () => {
  await fs.rm(tempRoot, { recursive: true, force: true });
});

async function baseBuild(incremental = true, clean = false): Promise<BuildStats[]> {
  const stats: BuildStats[] = [];
  await build({
    contentDir,
    outputDir,
    templateDir,
    incremental,
    clean,
    onStats: (s) => stats.push(s),
  });
  return stats;
}

describe('parseArgs incremental flags', () => {
  it('sets incremental and clean flags for build', () => {
    expect(
      parseArgs(['build', '--incremental', '--clean', '--output', 'out'])
    ).toEqual({
      contentDir: 'content',
      outputDir: 'out',
      templateDir: 'templates',
      incremental: true,
      clean: true,
    });
  });

  it('accepts --incremental without a value and rejects --content --incremental misuse', () => {
    expect(parseArgs(['build', '--incremental'])).toEqual({
      contentDir: 'content',
      outputDir: 'dist',
      templateDir: 'templates',
      incremental: true,
    });
    expect(parseArgs(['build', '--incremental', 'foo'])).toBe('invalid');
  });
});

describe('incremental build correctness', () => {
  it('builds every page on the first run and writes the cache manifest', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n\nFirst.\n');
    await writeSource('two.md', '---\ntitle: Two\n---\n\n# Two\n\nSecond.\n');

    const stats = await baseBuild();

    expect(stats).toHaveLength(1);
    expect(stats[0].incremental).toBe(true);
    expect(stats[0].built).toBe(2);
    expect(stats[0].skipped).toBe(0);

    expect(await readOutput('one.html')).toContain('<h1>One</h1>');
    expect(await readOutput('two.html')).toContain('<h1>Two</h1>');
    expect(await readOutput('index.html')).toContain('One');

    const manifest = await loadManifest(cacheFile);
    expect(manifest).not.toBeNull();
    expect(Object.keys(manifest!.entries).sort()).toEqual(['one.html', 'two.html']);
    const entry = manifest!.entries['one.html'];
    expect(entry.sourceHash).toMatch(/^[0-9a-f]{64}$/);
    expect(entry.templateHash).toBeDefined();
    expect(entry.html).toContain('<h1>One</h1>');
    expect(entry.page.title).toBe('One');
  });

  it('skips every page and the index on an unchanged second build', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await baseBuild();

    const before = await readOutput('one.html');
    const stats = await baseBuild();

    expect(stats[0].built).toBe(0);
    expect(stats[0].skipped).toBe(1);
    expect(stats[0].timeSavedMs).toBeGreaterThanOrEqual(0);

    expect(await readOutput('one.html')).toBe(before);
    expect(await readOutput('index.html')).toContain('One');

    const manifest = await loadManifest(cacheFile);
    expect(Object.keys(manifest!.entries).sort()).toEqual(['one.html']);
  });

  it('reuses cached frontmatter metadata for skipped pages', async () => {
    await writeSource('one.md', '---\ntitle: Original\n---\n\n# One\n');
    const firstPages = await build({
      contentDir,
      outputDir,
      templateDir,
      incremental: true,
    });
    expect(firstPages[0].title).toBe('Original');

    const secondPages = await build({
      contentDir,
      outputDir,
      templateDir,
      incremental: true,
    });
    expect(secondPages).toHaveLength(1);
    expect(secondPages[0].title).toBe('Original');
    expect(secondPages[0].data).toMatchObject({ title: 'Original' });
  });

  it('rebuilds only the changed page and the index when one source changes', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await writeSource('two.md', '---\ntitle: Two\n---\n\n# Two\n');
    await baseBuild();

    await writeSource('two.md', '---\ntitle: Two Updated\n---\n\n# Two Updated\n');
    const stats = await baseBuild();

    expect(stats[0].built).toBe(1);
    expect(stats[0].skipped).toBe(1);

    const twoHtml = await readOutput('two.html');
    expect(twoHtml).toContain('<h1>Two Updated</h1>');
    expect(await readOutput('one.html')).toContain('<h1>One</h1>');
    expect(await readOutput('index.html')).toContain('Two Updated');
  });

  it('rebuilds every page when a template changes', async () => {
    await fs.writeFile(
      path.join(templateDir, 'default.hbs'),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>',
      'utf8'
    );
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await writeSource('two.md', '---\ntitle: Two\n---\n\n# Two\n');
    await baseBuild();

    await fs.writeFile(
      path.join(templateDir, 'default.hbs'),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body class="new">{{{body}}}</body></html>',
      'utf8'
    );
    const stats = await baseBuild();

    expect(stats[0].built).toBe(2);
    expect(stats[0].skipped).toBe(0);
    expect(await readOutput('one.html')).toContain('class="new"');
    expect(await readOutput('two.html')).toContain('class="new"');
  });

  it('builds a newly added page while skipping unchanged ones', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await baseBuild();

    await writeSource('three.md', '---\ntitle: Three\n---\n\n# Three\n');
    const stats = await baseBuild();

    expect(stats[0].built).toBe(1);
    expect(stats[0].skipped).toBe(1);
    expect(await readOutput('three.html')).toContain('<h1>Three</h1>');
    expect(await readOutput('index.html')).toContain('Three');
  });

  it('removes the output of a deleted page', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await writeSource('two.md', '---\ntitle: Two\n---\n\n# Two\n');
    await baseBuild();
    expect(await readOutput('two.html')).toContain('Two');

    await fs.unlink(path.join(contentDir, 'two.md'));
    const stats = await baseBuild();

    expect(stats[0].built).toBe(0);
    expect(stats[0].skipped).toBe(1);

    await expect(fs.access(path.join(outputDir, 'two.html'))).rejects.toThrow();
    expect(await readOutput('one.html')).toContain('<h1>One</h1>');

    const manifest = await loadManifest(cacheFile);
    expect(Object.keys(manifest!.entries).sort()).toEqual(['one.html']);
  });

  it('rebuilds a page when its output file is missing from disk', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await baseBuild();

    await fs.unlink(path.join(outputDir, 'one.html'));
    const stats = await baseBuild();

    expect(stats[0].built).toBe(1);
    expect(stats[0].skipped).toBe(0);
    expect(await readOutput('one.html')).toContain('<h1>One</h1>');
  });

  it('forces a full rebuild when --clean is passed even with a warm cache', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await writeSource('two.md', '---\ntitle: Two\n---\n\n# Two\n');
    await baseBuild();

    const stats = await baseBuild(true, true);

    expect(stats[0].built).toBe(2);
    expect(stats[0].skipped).toBe(0);
    expect(stats[0].clean).toBe(true);
  });

  it('treats a missing cache as a clean full build', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    const first = await baseBuild();
    expect(first[0].built).toBe(1);
  });

  it('does not write a cache manifest for non-incremental builds', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await build({ contentDir, outputDir, templateDir });
    await expect(fs.access(cacheFile)).rejects.toThrow();
  });

  it('reports stats through onStats for incremental builds', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await baseBuild();

    const stats: BuildStats[] = [];
    await build({
      contentDir,
      outputDir,
      templateDir,
      incremental: true,
      onStats: (s) => stats.push(s),
    });
    expect(stats).toHaveLength(1);
    expect(stats[0].incremental).toBe(true);
    expect(stats[0].skipped).toBe(1);
    expect(stats[0].timeSavedMs).toBeGreaterThanOrEqual(0);
    expect(stats[0].durationMs).toBeGreaterThanOrEqual(0);
  });

  it('works together with a non-default cache file location', async () => {
    const customCache = path.join(tempRoot, 'custom-cache.json');
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await build({ contentDir, outputDir, templateDir, incremental: true, cacheFile: customCache });

    const stats: BuildStats[] = [];
    await build({
      contentDir,
      outputDir,
      templateDir,
      incremental: true,
      cacheFile: customCache,
      onStats: (s) => stats.push(s),
    });
    expect(stats[0].skipped).toBe(1);
    await expect(fs.access(customCache)).resolves.toBeUndefined();
  });

  it('ignores a corrupted cache manifest and rebuilds everything', async () => {
    await writeSource('one.md', '---\ntitle: One\n---\n\n# One\n');
    await baseBuild();

    await fs.writeFile(cacheFile, '{not valid json', 'utf8');
    const stats = await baseBuild();
    expect(stats[0].built).toBe(1);
  });
});

describe('incremental with templates from fixtures', () => {
  it('reuses cached HTML across incremental builds without changing output', async () => {
    await fs.cp(FIXTURES, tempRoot, { recursive: true });
    const srcContent = path.join(tempRoot, 'template-content');
    const srcTemplates = path.join(tempRoot, 'templates');
    const out = path.join(tempRoot, 'out');

    const first = await build({
      contentDir: srcContent,
      outputDir: out,
      templateDir: srcTemplates,
      incremental: true,
    });
    expect(first.map((page) => page.slug).sort()).toEqual(['about', 'hello', 'plain']);

    const before = await fs.readFile(path.join(out, 'hello.html'), 'utf8');
    const stats: BuildStats[] = [];
    await build({
      contentDir: srcContent,
      outputDir: out,
      templateDir: srcTemplates,
      incremental: true,
      onStats: (s) => stats.push(s),
    });
    expect(stats[0].built).toBe(0);
    expect(stats[0].skipped).toBe(3);
    expect(await fs.readFile(path.join(out, 'hello.html'), 'utf8')).toBe(before);
  });
});
