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
});
