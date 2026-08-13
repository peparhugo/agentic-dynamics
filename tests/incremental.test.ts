import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createEngine, Plugin } from '../src';

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
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<main>{{title}}:{{{body}}}</main>');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('creates a manifest and skips unchanged pages', async () => {
    const first = await createEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await first.build();
    const oneTime = (await fs.stat(path.join(outputDir, 'one.html'))).mtimeMs;
    const manifest = JSON.parse(await fs.readFile(path.join(outputDir, '.ssg-cache.json'), 'utf8'));

    await new Promise((resolve) => setTimeout(resolve, 20));
    const second = await createEngine({ contentDir, outputDir, templatesDir, incremental: true });
    const pages = await second.build();

    expect(Object.keys(manifest.pages)).toEqual(['one.md', 'two.md']);
    expect(pages.map((page) => page.title)).toEqual(['One', 'Two']);
    expect(second.lastBuildStats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });
    expect((await fs.stat(path.join(outputDir, 'one.html'))).mtimeMs).toBe(oneTime);
    expect(second.lastBuildStats.timeSavedMs).toBeGreaterThanOrEqual(0);
  });

  it('only rebuilds a changed source and uses cached frontmatter for the index', async () => {
    const first = await createEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await first.build();
    const twoTime = (await fs.stat(path.join(outputDir, 'two.html'))).mtimeMs;

    await new Promise((resolve) => setTimeout(resolve, 20));
    await fs.writeFile(path.join(contentDir, 'one.md'), '---\ntitle: Updated\n---\nChanged');
    const second = await createEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await second.build();

    expect(second.lastBuildStats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).resolves.toContain('Updated');
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('Two');
    expect((await fs.stat(path.join(outputDir, 'two.html'))).mtimeMs).toBe(twoTime);
  });

  it('invalidates every page when a template changes', async () => {
    await (await createEngine({ contentDir, outputDir, templatesDir, incremental: true })).build();
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{title}}:{{{body}}}</article>');

    const engine = await createEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await engine.build();

    expect(engine.lastBuildStats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).resolves.toContain('<article>');
  });

  it('does a clean build without a cache or with the clean option', async () => {
    const uncached = await createEngine({ contentDir, outputDir, templatesDir, incremental: true });
    await uncached.build();
    expect(uncached.lastBuildStats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });

    const clean = await createEngine({ contentDir, outputDir, templatesDir, incremental: true, clean: true });
    await clean.build();
    expect(clean.lastBuildStats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
  });

  it('removes output for deleted sources and retains plugin lifecycle hooks', async () => {
    const calls: string[] = [];
    const plugin: Plugin = {
      onStart: () => { calls.push('start'); },
      onFile: (page) => { calls.push(`file:${page.title}`); },
      afterBuild: (context) => { calls.push(`after:${context.pages.length}`); },
      onEnd: () => { calls.push('end'); },
    };
    await (await createEngine({ contentDir, outputDir, templatesDir, incremental: true, plugins: [plugin] })).build();
    calls.length = 0;
    await fs.rm(path.join(contentDir, 'two.md'));

    const engine = await createEngine({ contentDir, outputDir, templatesDir, incremental: true, plugins: [plugin] });
    await engine.build();

    expect(calls).toEqual(['start', 'after:1', 'end']);
    expect(engine.lastBuildStats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 1 });
    await expect(fs.access(path.join(outputDir, 'two.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });
});
