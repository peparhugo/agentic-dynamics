import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type Plugin } from '../src/index';

describe('plugin system', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugins-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Original\n---\n# Content');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('runs lifecycle hooks in plugin order and allows page transformation', async () => {
    const calls: string[] = [];
    const plugin = (name: string): Plugin => ({
      name,
      onStart: () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: (page) => {
        calls.push(`${name}:file`);
        page.title += name;
      },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); }
    });

    const pages = await buildSite({ contentDir, outputDir, configFile: false, plugins: [plugin('A'), plugin('B')] });

    expect(pages[0].title).toBe('OriginalAB');
    expect(await fs.readFile(path.join(outputDir, 'page.html'), 'utf8')).toContain('<title>OriginalAB</title>');
    expect(calls).toEqual([
      'A:start', 'B:start', 'A:before', 'B:before', 'A:file', 'B:file',
      'A:after', 'B:after', 'A:end', 'B:end'
    ]);
  });

  it('loads TypeScript plugin modules from ssg.config.ts', async () => {
    const pluginsDir = path.join(root, 'plugins');
    await fs.mkdir(pluginsDir);
    await fs.writeFile(path.join(pluginsDir, 'title.ts'), `
      import type { Plugin } from '${path.resolve('src/index').replaceAll('\\', '/')}';
      const plugin: Plugin = { onFile(page) { page.title = 'Configured'; } };
      export default plugin;
    `);
    await fs.writeFile(path.join(root, 'ssg.config.ts'), `
      import plugin from './plugins/title';
      export default { plugins: [plugin] };
    `);

    const pages = await buildSite({ contentDir, outputDir, configFile: path.join(root, 'ssg.config.ts') });

    expect(pages[0].title).toBe('Configured');
    expect(await fs.readFile(path.join(outputDir, 'page.html'), 'utf8')).toContain('<title>Configured</title>');
  });
});
