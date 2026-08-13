import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSiteWithStats, type Plugin } from '../src/index';

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
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('skips unchanged pages and restores their metadata for the index', async () => {
    const visited: string[] = [];
    const plugin: Plugin = { onFile(page) { visited.push(page.sourcePath); } };
    const options = { contentDir, outputDir, templatesDir, incremental: true, configFile: false as const, plugins: [plugin] };

    const first = await buildSiteWithStats(options);
    const firstHtml = await fs.readFile(path.join(outputDir, 'one.html'), 'utf8');
    const second = await buildSiteWithStats(options);

    expect(first.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    expect(second.stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 2 }));
    expect(second.stats.timeSavedMs).toBeGreaterThan(0);
    expect(visited).toEqual(['one.md', 'two.md']);
    expect(await fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).toBe(firstHtml);
    expect(await fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).toContain('One');
    await expect(fs.stat(path.join(outputDir, '.ssg-cache.json'))).resolves.toBeDefined();
  });

  it('rebuilds only a changed source page and removes deleted output', async () => {
    const options = { contentDir, outputDir, templatesDir, incremental: true, configFile: false as const };
    await buildSiteWithStats(options);
    await fs.writeFile(path.join(contentDir, 'one.md'), '---\ntitle: Updated\n---\nChanged');

    const result = await buildSiteWithStats(options);

    expect(result.stats).toEqual(expect.objectContaining({ pagesBuilt: 1, pagesSkipped: 1 }));
    expect(await fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).toContain('Updated');

    await fs.rm(path.join(contentDir, 'two.md'));
    const afterDelete = await buildSiteWithStats(options);
    expect(afterDelete.stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 1 }));
    await expect(fs.stat(path.join(outputDir, 'two.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  it('invalidates all pages when a template changes', async () => {
    const options = { contentDir, outputDir, templatesDir, incremental: true, configFile: false as const };
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<main>{{title}} {{{content}}}</main>');
    await buildSiteWithStats(options);
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{title}} {{{content}}}</article>');

    const result = await buildSiteWithStats(options);

    expect(result.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    expect(await fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).toContain('<article>One');
  });

  it('performs clean builds when the cache is missing or clean is requested', async () => {
    const options = { contentDir, outputDir, templatesDir, incremental: true, configFile: false as const };
    await buildSiteWithStats(options);
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'stale');
    await fs.rm(path.join(outputDir, '.ssg-cache.json'));

    const missing = await buildSiteWithStats(options);
    expect(missing.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    await expect(fs.stat(path.join(outputDir, 'stale.html'))).rejects.toMatchObject({ code: 'ENOENT' });

    const clean = await buildSiteWithStats({ ...options, clean: true });
    expect(clean.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
  });
});
