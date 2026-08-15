import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import { buildWithStats } from '../src';
import { CacheManager, CACHE_FILENAME } from '../src/cache';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incr-'));
}

async function writeFile(filePath: string, contents: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, contents, 'utf8');
}

async function setupContent(contentDir: string): Promise<void> {
  await writeFile(
    path.join(contentDir, 'alpha.md'),
    '---\ntitle: Alpha\n---\n# First alpha'
  );
  await writeFile(
    path.join(contentDir, 'beta.md'),
    '---\ntitle: Beta\n---\n# First beta'
  );
}

describe('incremental builds', () => {
  it('does a clean build when the cache is missing', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    await setupContent(contentDir);

    const first = await buildWithStats({
      content: contentDir,
      output: outputDir,
      incremental: true,
    });

    expect(first.pages).toHaveLength(2);
    expect(first.stats.pagesBuilt).toBe(2);
    expect(first.stats.pagesSkipped).toBe(0);
    expect(first.stats.timeSavedMs).toBe(0);

    const cache = new CacheManager(outputDir);
    const manifest = await cache.load();
    expect(manifest).toBeDefined();
    expect(Object.keys(manifest!.pages)).toHaveLength(2);
  });

  it('skips unchanged pages on a second incremental build', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    await setupContent(contentDir);

    await buildWithStats({ content: contentDir, output: outputDir, incremental: true });

    const second = await buildWithStats({
      content: contentDir,
      output: outputDir,
      incremental: true,
    });

    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    expect(second.stats.timeSavedMs).toBeGreaterThanOrEqual(0);

    const alphaHtml = await fs.readFile(path.join(outputDir, 'alpha.html'), 'utf8');
    expect(alphaHtml).toContain('<h1>First alpha</h1>');
  });

  it('rebuilds only the changed page and reuses frontmatter for the rest', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    await setupContent(contentDir);

    await buildWithStats({ content: contentDir, output: outputDir, incremental: true });

    await writeFile(
      path.join(contentDir, 'alpha.md'),
      '---\ntitle: Alpha Updated\n---\n# Second alpha'
    );

    const result = await buildWithStats({
      content: contentDir,
      output: outputDir,
      incremental: true,
    });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    const alphaHtml = await fs.readFile(path.join(outputDir, 'alpha.html'), 'utf8');
    expect(alphaHtml).toContain('<h1>Second alpha</h1>');
    expect(alphaHtml).toContain('<title>Alpha Updated</title>');

    const betaHtml = await fs.readFile(path.join(outputDir, 'beta.html'), 'utf8');
    expect(betaHtml).toContain('<h1>First beta</h1>');
  });

  it('rebuilds all pages when a template changes', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    const templatesDir = await makeTempDir();
    await setupContent(contentDir);

    await writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body>{{{body}}}</body></html>'
    );

    await buildWithStats({
      content: contentDir,
      output: outputDir,
      templates: templatesDir,
      incremental: true,
    });

    await writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body class="v2">{{{body}}}</body></html>'
    );

    const result = await buildWithStats({
      content: contentDir,
      output: outputDir,
      templates: templatesDir,
      incremental: true,
    });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const alphaHtml = await fs.readFile(path.join(outputDir, 'alpha.html'), 'utf8');
    expect(alphaHtml).toContain('class="v2"');
  });

  it('forces a clean build with --clean even when the cache exists', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    await setupContent(contentDir);

    await buildWithStats({ content: contentDir, output: outputDir, incremental: true });

    const result = await buildWithStats({
      content: contentDir,
      output: outputDir,
      incremental: true,
      clean: true,
    });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('writes the manifest to .ssg-cache.json in the output directory', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    await setupContent(contentDir);

    await buildWithStats({ content: contentDir, output: outputDir, incremental: true });

    const cachePath = path.join(outputDir, CACHE_FILENAME);
    const raw = await fs.readFile(cachePath, 'utf8');
    const manifest = JSON.parse(raw);
    expect(manifest.version).toBe(1);
    expect(manifest.templatesHash).toEqual(expect.any(String));
  });

  it('does not skip pages when running a non-incremental build', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    await setupContent(contentDir);

    const first = await buildWithStats({ content: contentDir, output: outputDir });
    expect(first.stats.pagesBuilt).toBe(2);
    expect(first.stats.pagesSkipped).toBe(0);

    const second = await buildWithStats({ content: contentDir, output: outputDir });
    expect(second.stats.pagesBuilt).toBe(2);
    expect(second.stats.pagesSkipped).toBe(0);
  });
});
