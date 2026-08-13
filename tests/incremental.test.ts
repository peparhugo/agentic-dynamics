import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSiteWithStats } from '../src/generator.js';
import type { Plugin } from '../src/plugin.js';

describe('incremental builds', () => {
  it('rebuilds only pages whose sources changed', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'site');
    await mkdir(content);
    await writeFile(join(content, 'first.md'), '---\ntitle: First\n---\nOriginal');
    await writeFile(join(content, 'second.md'), '---\ntitle: Second\n---\nUnchanged');
    await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true });
    const calls: string[] = [];
    const plugin: Plugin = { onFile: (page) => calls.push(page.slug) };

    const unchanged = await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true, plugins: [plugin] });
    expect(unchanged.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });
    expect(calls).toEqual([]);

    await writeFile(join(content, 'first.md'), '---\ntitle: First\n---\nUpdated');
    const changed = await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true, plugins: [plugin] });
    expect(changed.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(calls).toEqual(['first']);
    await expect(readFile(join(output, 'first.html'), 'utf8')).resolves.toContain('<p>Updated</p>');
    await expect(readFile(join(output, 'second.html'), 'utf8')).resolves.toContain('<p>Unchanged</p>');
  });

  it('invalidates every page when a template changes and cleans when requested', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'site');
    await mkdir(content);
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page');
    await writeFile(join(templates, 'page.hbs'), '<main>{{{content}}}</main>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<body>{{{body}}}</body>');
    await buildSiteWithStats({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    await writeFile(join(templates, 'page.hbs'), '<article>{{{content}}}</article>');

    const result = await buildSiteWithStats({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    expect(result.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toContain('<article>');

    const clean = await buildSiteWithStats({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, clean: true });
    expect(clean.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
  });
});
