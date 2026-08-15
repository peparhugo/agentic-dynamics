import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build, buildWithStats } from '../src/generator';
import { BuildStats } from '../src/types';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incr-test-'));
}

async function write(dir: string, name: string, content: string): Promise<void> {
  const full = path.join(dir, name);
  await fs.mkdir(path.dirname(full), { recursive: true });
  await fs.writeFile(full, content, 'utf8');
}

interface Site {
  root: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  cacheFile: string;
}

async function makeSite(): Promise<Site> {
  const root = await makeTempDir();
  const site: Site = {
    root,
    contentDir: path.join(root, 'content'),
    outputDir: path.join(root, 'dist'),
    templatesDir: path.join(root, 'templates'),
    cacheFile: path.join(root, '.ssg-cache.json'),
  };
  await write(site.contentDir, 'one.md', ['---', 'title: One', '---', '# One'].join('\n'));
  await write(site.contentDir, 'two.md', ['---', 'title: Two', '---', '# Two'].join('\n'));
  return site;
}

async function incrementalBuild(site: Site) {
  return buildWithStats({
    contentDir: site.contentDir,
    outputDir: site.outputDir,
    templatesDir: site.templatesDir,
    incremental: true,
    cacheFile: site.cacheFile,
  });
}

async function readManifest(site: Site): Promise<{ files: Record<string, unknown> }> {
  return JSON.parse(await fs.readFile(site.cacheFile, 'utf8'));
}

describe('incremental builds', () => {
  it('creates a .ssg-cache.json manifest on the first incremental build', async () => {
    const site = await makeSite();
    await incrementalBuild(site);

    expect(await fs.stat(site.cacheFile)).toBeDefined();
    const manifest = await readManifest(site);
    expect(Object.keys(manifest.files)).toEqual(expect.arrayContaining(['one', 'two']));
    expect(manifest.files.one).toMatchObject({
      sourceHash: expect.any(String),
      templateHash: expect.any(String),
      html: expect.stringContaining('<h1>One</h1>'),
    });
  });

  it('builds every page plus the index on a fresh cache', async () => {
    const site = await makeSite();
    const { pages, stats } = await incrementalBuild(site);

    expect(pages).toHaveLength(2);
    expect(stats.built).toBe(3);
    expect(stats.skipped).toBe(0);
    expect(stats.timeSavedMs).toBe(0);

    const one = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    const two = await fs.readFile(path.join(site.outputDir, 'two.html'), 'utf8');
    const index = await fs.readFile(path.join(site.outputDir, 'index.html'), 'utf8');
    expect(one).toContain('<h1>One</h1>');
    expect(two).toContain('<h1>Two</h1>');
    expect(index).toContain('href="one.html"');
    expect(index).toContain('href="two.html"');
  });

  it('skips unchanged pages on the second build and reuses cached HTML', async () => {
    const site = await makeSite();
    await incrementalBuild(site);

    const before = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    const second = await incrementalBuild(site);

    expect(second.stats.built).toBe(1);
    expect(second.stats.skipped).toBe(2);

    const after = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    expect(after).toBe(before);

    const manifest = await readManifest(site);
    const expectedSaved =
      (manifest.files.one as { renderMs: number }).renderMs +
      (manifest.files.two as { renderMs: number }).renderMs;
    expect(second.stats.timeSavedMs).toBeCloseTo(expectedSaved, 1);
  });

  it('only rebuilds the page whose source changed', async () => {
    const site = await makeSite();
    await incrementalBuild(site);

    await write(site.contentDir, 'two.md', ['---', 'title: Two Updated', '---', '# Two Updated'].join('\n'));
    const second = await incrementalBuild(site);

    expect(second.stats.built).toBe(2);
    expect(second.stats.skipped).toBe(1);

    const two = await fs.readFile(path.join(site.outputDir, 'two.html'), 'utf8');
    expect(two).toContain('Two Updated');
    const one = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    expect(one).toContain('<h1>One</h1>');
  });

  it('rebuilds a page when its frontmatter changes', async () => {
    const site = await makeSite();
    await incrementalBuild(site);

    await write(site.contentDir, 'one.md', ['---', 'title: One Renamed', '---', '# One'].join('\n'));
    const second = await incrementalBuild(site);

    expect(second.stats.skipped).toBe(1);
    expect(second.stats.built).toBe(2);

    const one = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    expect(one).toContain('One Renamed');
  });

  it('adds new pages while skipping existing ones', async () => {
    const site = await makeSite();
    await incrementalBuild(site);

    await write(site.contentDir, 'three.md', ['---', 'title: Three', '---', '# Three'].join('\n'));
    const second = await incrementalBuild(site);

    expect(second.stats.built).toBe(2);
    expect(second.stats.skipped).toBe(2);

    const three = await fs.readFile(path.join(site.outputDir, 'three.html'), 'utf8');
    expect(three).toContain('<h1>Three</h1>');
    const index = await fs.readFile(path.join(site.outputDir, 'index.html'), 'utf8');
    expect(index).toContain('href="three.html"');
  });

  it('rebuilds every page when a shared template changes', async () => {
    const site = await makeSite();
    await write(site.templatesDir, 'default.hbs', 'ORIGINAL {{title}}: {{{html}}}');
    await incrementalBuild(site);

    await write(site.templatesDir, 'default.hbs', 'REVISED {{title}}: {{{html}}}');
    const second = await incrementalBuild(site);

    expect(second.stats.built).toBe(3);
    expect(second.stats.skipped).toBe(0);

    const one = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    expect(one).toContain('REVISED One');
  });

  it('only rebuilds pages that use a changed per-page template', async () => {
    const site = await makeSite();
    await write(site.templatesDir, 'default.hbs', 'DEFAULT {{title}}');
    await write(site.templatesDir, 'post.hbs', 'POST {{title}}');
    await write(
      site.contentDir,
      'one.md',
      ['---', 'title: One', 'template: post', '---', '# One'].join('\n')
    );
    await incrementalBuild(site);

    await write(site.templatesDir, 'post.hbs', 'POST-REVISED {{title}}');
    const second = await incrementalBuild(site);

    expect(second.stats.built).toBe(2);
    expect(second.stats.skipped).toBe(1);

    const one = await fs.readFile(path.join(site.outputDir, 'one.html'), 'utf8');
    expect(one).toContain('POST-REVISED One');
    const two = await fs.readFile(path.join(site.outputDir, 'two.html'), 'utf8');
    expect(two).toContain('DEFAULT Two');
  });

  it('--clean forces a full rebuild even with a valid cache', async () => {
    const site = await makeSite();
    await incrementalBuild(site);

    const clean = await buildWithStats({
      contentDir: site.contentDir,
      outputDir: site.outputDir,
      templatesDir: site.templatesDir,
      incremental: true,
      clean: true,
      cacheFile: site.cacheFile,
    });

    expect(clean.stats.built).toBe(3);
    expect(clean.stats.skipped).toBe(0);
    expect(await fs.stat(site.cacheFile)).toBeDefined();
  });

  it('falls back to a full build when the cache is missing', async () => {
    const site = await makeSite();
    const first = await incrementalBuild(site);
    expect(first.stats.built).toBe(3);
    expect(first.stats.skipped).toBe(0);
  });

  it('does not write a cache manifest for non-incremental builds', async () => {
    const site = await makeSite();
    await build({
      contentDir: site.contentDir,
      outputDir: site.outputDir,
      templatesDir: site.templatesDir,
    });
    await expect(fs.stat(site.cacheFile)).rejects.toThrow();
  });
});
