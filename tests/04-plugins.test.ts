import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, createSsg, type Plugin } from '../src/index';

describe('plugin pipeline', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugins-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Original\n---\nBody');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('runs lifecycle hooks in plugin order', async () => {
    const calls: string[] = [];
    const plugin = (name: string): Plugin => ({
      onStart: () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: (page) => { calls.push(`${name}:file:${page.title}`); },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); },
    });

    await buildSite({ contentDir, outputDir, plugins: [plugin('first'), plugin('second')] });

    expect(calls).toEqual([
      'first:start', 'second:start',
      'first:before', 'second:before',
      'first:file:Original', 'second:file:Original',
      'first:after', 'second:after',
      'first:end', 'second:end',
    ]);
  });

  it('starts once, runs build hooks on rebuilds, and ends once', async () => {
    const calls: string[] = [];
    const ssg = createSsg({
      contentDir,
      outputDir,
      plugins: [{
        onStart: () => { calls.push('start'); },
        beforeBuild: () => { calls.push('before'); },
        afterBuild: () => { calls.push('after'); },
        onEnd: () => { calls.push('end'); },
      }],
    });

    await ssg.build();
    await ssg.build();
    await ssg.close();
    await ssg.close();

    expect(calls).toEqual(['start', 'before', 'after', 'before', 'after', 'end']);
  });

  it('loads TypeScript plugins from ssg.config.ts', async () => {
    const pluginsDir = path.join(root, 'plugins');
    await fs.mkdir(pluginsDir);
    await fs.writeFile(path.join(pluginsDir, 'title.ts'), `
      export default {
        onFile(page: { title: string }) { page.title = 'Configured'; }
      };
    `);
    await fs.writeFile(path.join(root, 'ssg.config.ts'), `
      import titlePlugin from './plugins/title';
      export default { plugins: [titlePlugin] };
    `);

    const pages = await buildSite({
      contentDir,
      outputDir,
      configFile: path.join(root, 'ssg.config.ts'),
    });

    expect(pages[0].title).toBe('Configured');
    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8')).resolves.toContain('<h1>Configured</h1>');
  });
});
