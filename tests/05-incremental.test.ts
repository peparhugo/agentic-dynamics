import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type BuildStats, type Plugin } from '../src/index';
import { parseArgs } from '../src/cli';

describe('incremental builds', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incremental-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(contentDir, 'one.md'), '---\ntitle: One\n---\nFirst');
    await fs.writeFile(path.join(contentDir, 'two.md'), '---\ntitle: Two\n---\nSecond');
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{title}}: {{{content}}}</article>');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('parses incremental and clean CLI flags', () => {
    expect(parseArgs(['build', '--incremental', '--clean'])).toEqual({
      command: 'build', incremental: true, clean: true,
    });
  });

  it('skips unchanged pages and preserves their output files', async () => {
    const stats: BuildStats[] = [];
    const options = { contentDir, outputDir, templatesDir, incremental: true, onBuildStats: (value: BuildStats) => stats.push(value) };
    await buildSite(options);
    const outputPath = path.join(outputDir, 'one.html');
    const firstModified = (await fs.stat(outputPath)).mtimeMs;
    await new Promise((resolve) => setTimeout(resolve, 20));
    await buildSite(options);

    expect(stats.map(({ pagesBuilt, pagesSkipped }) => [pagesBuilt, pagesSkipped])).toEqual([[2, 0], [0, 2]]);
    expect(stats[1].timeSavedMs).toBeGreaterThanOrEqual(0);
    expect((await fs.stat(outputPath)).mtimeMs).toBe(firstModified);
    const manifest = JSON.parse(await fs.readFile(path.join(root, '.ssg-cache.json'), 'utf8')) as { pages: object };
    expect(Object.keys(manifest.pages)).toEqual(['one.md', 'two.md']);
  });

  it('rebuilds only a changed source and reruns file plugins for it', async () => {
    let processed = 0;
    const plugin: Plugin = { onFile: () => { processed += 1; } };
    let stats: BuildStats | undefined;
    const options = { contentDir, outputDir, templatesDir, plugins: [plugin], incremental: true, onBuildStats: (value: BuildStats) => { stats = value; } };
    await buildSite(options);
    processed = 0;
    await fs.writeFile(path.join(contentDir, 'one.md'), '---\ntitle: Changed\n---\nUpdated');
    await buildSite(options);

    expect(processed).toBe(1);
    expect(stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(await fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).toContain('Changed');
  });

  it('invalidates pages when their template changes', async () => {
    let stats: BuildStats | undefined;
    const options = { contentDir, outputDir, templatesDir, incremental: true, onBuildStats: (value: BuildStats) => { stats = value; } };
    await buildSite(options);
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<main>{{title}}</main>');
    await buildSite(options);

    expect(stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(await fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).toBe('<main>One</main>');
  });

  it('performs full builds when the cache is missing or clean is requested', async () => {
    const stats: BuildStats[] = [];
    const base = { contentDir, outputDir, templatesDir, incremental: true, onBuildStats: (value: BuildStats) => stats.push(value) };
    await buildSite(base);
    await fs.rm(path.join(root, '.ssg-cache.json'));
    await buildSite(base);
    await buildSite({ ...base, clean: true });

    expect(stats.map(({ pagesBuilt, pagesSkipped }) => [pagesBuilt, pagesSkipped])).toEqual([[2, 0], [2, 0], [2, 0]]);
  });
});
