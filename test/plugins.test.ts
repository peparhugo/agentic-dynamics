import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';
import type { Plugin } from '../src/plugin';

describe('plugins', () => {
  let directory: string;
  let content: string;
  let output: string;

  beforeEach(async () => {
    directory = await mkdtemp(path.join(os.tmpdir(), 'ssg-plugins-'));
    content = path.join(directory, 'content');
    output = path.join(directory, 'dist');
    await mkdir(content);
    await writeFile(path.join(content, 'page.md'), '---\ntitle: Page\n---\nContent');
  });

  afterEach(async () => rm(directory, { recursive: true, force: true }));

  it('runs lifecycle hooks in plugin order', async () => {
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

    await buildSite({ contentDir: content, outputDir: output, plugins: [first, second] });

    expect(calls).toEqual([
      'first:start', 'second:start',
      'first:before', 'second:before',
      'first:file', 'second:file',
      'first:after', 'second:after',
      'first:end', 'second:end',
    ]);
  });

  it('lets plugins observe generated pages', async () => {
    const seen: string[] = [];
    await buildSite({
      contentDir: content,
      outputDir: output,
      plugins: [{ onFile: (page) => { seen.push(page.slug); } }],
    });

    expect(seen).toEqual(['page']);
    await expect(readFile(path.join(output, 'page.html'), 'utf8')).resolves.toContain('<p>Content</p>');
  });
});
