import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createEngine } from './engine';
import type { Plugin } from './plugins';

describe('SsgEngine', () => {
  it('runs every lifecycle hook in plugin order', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-engine-'));
    const content = join(root, 'content');
    const output = join(root, 'dist');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page', 'utf8');
    const calls: string[] = [];
    const first: Plugin = {
      onStart: () => { calls.push('first:start'); },
      beforeBuild: () => { calls.push('first:before'); },
      onFile: () => { calls.push('first:file'); },
      afterBuild: () => { calls.push('first:after'); },
      onEnd: () => { calls.push('first:end'); },
    };
    const second: Plugin = {
      onStart: () => { calls.push('second:start'); },
      beforeBuild: () => { calls.push('second:before'); },
      onFile: () => { calls.push('second:file'); },
      afterBuild: () => { calls.push('second:after'); },
      onEnd: () => { calls.push('second:end'); },
    };

    await (await createEngine([first, second])).build({ contentDir: content, outputDir: output });

    expect(calls).toEqual([
      'first:start', 'second:start', 'first:before', 'second:before',
      'first:file', 'second:file', 'first:after', 'second:after', 'first:end', 'second:end',
    ]);
  });

  it('loads plugins from ssg.config.ts', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-config-'));
    const content = join(root, 'content');
    const output = join(root, 'dist');
    const config = join(process.cwd(), 'ssg.config.ts');
    if (existsSync(config)) return;
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page', 'utf8');
    await writeFile(config, `export default [{ onFile(page) { page.html += '<p>Configured</p>'; } }];`, 'utf8');

    try {
      await (await createEngine()).build({ contentDir: content, outputDir: output });
      await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toContain('<p>Configured</p>');
    } finally {
      await rm(config, { force: true });
    }
  });

  it('rebuilds only changed sources during an incremental build', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-incremental-'));
    const content = join(root, 'content');
    const output = join(root, 'dist');
    await mkdir(content, { recursive: true });
    const first = join(content, 'first.md');
    const second = join(content, 'second.md');
    await writeFile(first, '# First', 'utf8');
    await writeFile(second, '# Second', 'utf8');
    const processed: string[] = [];
    const plugin: Plugin = { onFile: (page) => { processed.push(page.source); } };
    const engine = await createEngine([plugin]);

    await engine.build({ contentDir: content, outputDir: output, incremental: true });
    expect(engine.lastBuildStats).toEqual({ pagesBuilt: 2, pagesSkipped: 0, timeSavedMs: expect.any(Number) });
    processed.length = 0;
    await writeFile(first, '# Updated', 'utf8');

    await engine.build({ contentDir: content, outputDir: output, incremental: true });

    expect(processed).toEqual([first]);
    expect(engine.lastBuildStats).toEqual({ pagesBuilt: 1, pagesSkipped: 1, timeSavedMs: expect.any(Number) });
    await expect(readFile(join(output, 'first.html'), 'utf8')).resolves.toContain('<h1>Updated</h1>');
    await expect(readFile(join(output, 'second.html'), 'utf8')).resolves.toContain('<h1>Second</h1>');
  });

  it('invalidates cached pages when templates change and honors clean builds', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-incremental-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'dist');
    await mkdir(content, { recursive: true });
    await mkdir(templates, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page', 'utf8');
    await writeFile(join(templates, 'default.hbs'), '<article>{{{content}}}</article>', 'utf8');
    const processed: string[] = [];
    const engine = await createEngine([{ onFile: (page) => { processed.push(page.source); } }]);

    await engine.build({ contentDir: content, outputDir: output, templateDir: templates, incremental: true });
    processed.length = 0;
    await engine.build({ contentDir: content, outputDir: output, templateDir: templates, incremental: true });
    expect(processed).toEqual([]);
    await writeFile(join(templates, 'default.hbs'), '<section>{{{content}}}</section>', 'utf8');

    await engine.build({ contentDir: content, outputDir: output, templateDir: templates, incremental: true });
    expect(processed).toEqual([join(content, 'page.md')]);
    await expect(readFile(join(output, 'page.html'), 'utf8')).resolves.toContain('<section><h1>Page</h1>');
    processed.length = 0;
    await engine.build({ contentDir: content, outputDir: output, templateDir: templates, incremental: true, clean: true });
    expect(processed).toEqual([join(content, 'page.md')]);
  });
});
