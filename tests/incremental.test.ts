import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type Plugin } from '../src';

describe('incremental builds', () => {
  let root: string;
  let content: string;
  let output: string;
  let templates: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incremental-'));
    content = path.join(root, 'content');
    output = path.join(root, 'dist');
    templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'one.md'), '---\ntitle: One\n---\nFirst');
    await fs.writeFile(path.join(content, 'two.md'), '---\ntitle: Two\n---\nSecond');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('builds clean without a manifest and skips unchanged pages afterward', async () => {
    const first = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    const one = path.join(output, 'one.html');
    const initialTime = (await fs.stat(one)).mtimeMs;
    await new Promise((resolve) => setTimeout(resolve, 20));
    const second = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    expect(first.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    expect(second.stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 2 }));
    expect((await fs.stat(one)).mtimeMs).toBe(initialTime);
    const manifest = JSON.parse(await fs.readFile(path.join(root, '.ssg-cache.json'), 'utf8'));
    expect(manifest.pages['one.html']).toEqual(expect.objectContaining({ sourceHash: expect.any(String), html: expect.any(String) }));
  });

  test('treats an invalid manifest as a clean build', async () => {
    await fs.writeFile(path.join(root, '.ssg-cache.json'), 'null');

    const result = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    expect(result.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
  });

  test('rebuilds only a changed source and removes deleted page output', async () => {
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    await fs.writeFile(path.join(content, 'one.md'), '---\ntitle: Updated\n---\nChanged');
    await fs.rm(path.join(content, 'two.md'));

    const result = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    expect(result.stats).toEqual(expect.objectContaining({ pagesBuilt: 1, pagesSkipped: 0 }));
    await expect(fs.readFile(path.join(output, 'one.html'), 'utf8')).resolves.toContain('<title>Updated</title>');
    await expect(fs.stat(path.join(output, 'two.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  test('invalidates selected templates and partials but not unrelated templates', async () => {
    await fs.mkdir(path.join(templates, 'partials'));
    await fs.writeFile(path.join(templates, 'a.hbs'), '{{> shared}} {{{content}}}');
    await fs.writeFile(path.join(templates, 'unused.hbs'), 'unused');
    await fs.writeFile(path.join(templates, 'partials', 'shared.hbs'), '<b>{{title}}</b>');
    await fs.writeFile(path.join(content, 'one.md'), '---\ntitle: One\ntemplate: a\n---\nFirst');
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });

    await fs.writeFile(path.join(templates, 'unused.hbs'), 'changed but unused');
    const unrelated = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    expect(unrelated.stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 2 }));

    await fs.writeFile(path.join(templates, 'partials', 'shared.hbs'), '<strong>{{title}}</strong>');
    const partial = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    expect(partial.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    await expect(fs.readFile(path.join(output, 'one.html'), 'utf8')).resolves.toContain('<strong>One</strong>');
  });

  test('--clean behavior rebuilds every page while preserving plugin hooks', async () => {
    const onFile = jest.fn();
    const afterBuild = jest.fn();
    const plugin: Plugin = { name: 'test', onFile, afterBuild };
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, plugins: [plugin] });
    onFile.mockClear();

    const result = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, clean: true, plugins: [plugin] });

    expect(result.stats).toEqual(expect.objectContaining({ pagesBuilt: 2, pagesSkipped: 0 }));
    expect(onFile).toHaveBeenCalledTimes(2);
    expect(afterBuild).toHaveBeenCalledTimes(2);
  });
});
