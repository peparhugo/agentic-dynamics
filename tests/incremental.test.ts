import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { SsgEngine } from '../src/engine';
import { Plugin } from '../src/plugin';

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
    await fs.writeFile(path.join(contentDir, 'one.md'), '# One');
    await fs.writeFile(path.join(contentDir, 'two.md'), '# Two');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  async function build(clean = false): Promise<SsgEngine> {
    const engine = new SsgEngine({ contentDir, outputDir, templatesDir, incremental: true, clean });
    await engine.build();
    await engine.stop();
    return engine;
  }

  it('creates a manifest, then skips unchanged pages', async () => {
    const first = await build();
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.readFile(path.join(root, '.ssg-cache.json'), 'utf8')).resolves.toContain('sourceHash');

    const output = path.join(outputDir, 'one.html');
    const firstModified = (await fs.stat(output)).mtimeMs;
    await new Promise((resolve) => setTimeout(resolve, 20));
    const second = await build();

    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    expect((await fs.stat(output)).mtimeMs).toBe(firstModified);
  });

  it('only rebuilds a changed source page', async () => {
    await build();
    await fs.writeFile(path.join(contentDir, 'one.md'), '# Updated');

    const engine = await build();

    expect(engine.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).resolves.toContain('<h1>Updated</h1>');
    await expect(fs.readFile(path.join(outputDir, 'two.html'), 'utf8')).resolves.toContain('<h1>Two</h1>');
  });

  it('invalidates all pages when a template changes', async () => {
    const template = path.join(templatesDir, 'default.hbs');
    await fs.writeFile(template, '<main>{{{content}}}</main>');
    await build();
    await fs.writeFile(template, '<article>{{{content}}}</article>');

    const engine = await build();

    expect(engine.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.readFile(path.join(outputDir, 'one.html'), 'utf8')).resolves.toContain('<article>');
  });

  it('removes output and manifest entries for deleted sources', async () => {
    await build();
    await fs.rm(path.join(contentDir, 'two.md'));

    const engine = await build();

    expect(engine.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 1 });
    await expect(fs.access(path.join(outputDir, 'two.html'))).rejects.toThrow();
    const manifest = JSON.parse(await fs.readFile(path.join(root, '.ssg-cache.json'), 'utf8')) as { pages: Record<string, unknown> };
    expect(Object.keys(manifest.pages)).toEqual(['one.md']);
  });

  it('removes the prior output when a plugin changes its path', async () => {
    const source = path.join(contentDir, 'one.md');
    const plugin = (directory: string): Plugin => ({
      onFile(page) {
        if (page.filePath === source) page.outputPath = path.join(outputDir, directory, 'one.html');
      }
    });
    let engine = new SsgEngine({ contentDir, outputDir, templatesDir, incremental: true }, [plugin('old')]);
    await engine.build();
    await engine.stop();
    await fs.writeFile(source, '# Changed');

    engine = new SsgEngine({ contentDir, outputDir, templatesDir, incremental: true }, [plugin('new')]);
    await engine.build();
    await engine.stop();

    await expect(fs.access(path.join(outputDir, 'old', 'one.html'))).rejects.toThrow();
    await expect(fs.readFile(path.join(outputDir, 'new', 'one.html'), 'utf8')).resolves.toContain('<h1>Changed</h1>');
  });

  it('does a clean build without a cache or when clean is requested', async () => {
    await fs.mkdir(outputDir);
    await fs.writeFile(path.join(outputDir, 'stale.html'), 'stale');
    const first = await build();
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(fs.access(path.join(outputDir, 'stale.html'))).rejects.toThrow();

    const clean = await build(true);
    expect(clean.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
  });
});
