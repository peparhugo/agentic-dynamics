import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator.js';
import type { Plugin } from '../src/plugin.js';

describe('plugin pipeline', () => {
  it('runs every lifecycle hook in plugin order', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    await mkdir(content);
    await writeFile(join(content, 'page.md'), '# Page');
    const calls: string[] = [];
    const first: Plugin = {
      onStart: () => calls.push('first:start'),
      beforeBuild: () => calls.push('first:before'),
      onFile: () => calls.push('first:file'),
      afterBuild: () => calls.push('first:after'),
      onEnd: () => calls.push('first:end'),
    };
    const second: Plugin = {
      onStart: () => calls.push('second:start'),
      beforeBuild: () => calls.push('second:before'),
      onFile: () => calls.push('second:file'),
      afterBuild: () => calls.push('second:after'),
      onEnd: () => calls.push('second:end'),
    };

    await buildSite({ contentDir: content, outputDir: join(root, 'site'), plugins: [first, second] });

    expect(calls).toEqual([
      'first:start', 'second:start', 'first:before', 'second:before',
      'first:file', 'second:file', 'first:after', 'second:after', 'first:end', 'second:end',
    ]);
  });
});
