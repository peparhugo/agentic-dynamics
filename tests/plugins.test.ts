import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, Plugin } from '../src';

describe('plugin pipeline', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugins-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\n# Body');
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('runs every lifecycle hook in plugin order', async () => {
    const calls: string[] = [];
    const makePlugin = (name: string): Plugin => ({
      name,
      onStart: () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: (page) => { calls.push(`${name}:file`); page.html += `<!-- ${name} -->`; },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); },
    });

    await buildSite({ contentDir, outputDir, plugins: [makePlugin('first'), makePlugin('second')] });

    expect(calls).toEqual([
      'first:start', 'second:start',
      'first:before', 'second:before',
      'first:file', 'second:file',
      'first:after', 'second:after',
      'first:end', 'second:end',
    ]);
    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8'))
      .resolves.toContain('<!-- first --><!-- second -->');
  });

  it('loads ordered plugins from a TypeScript config', async () => {
    const configFile = path.join(root, 'ssg.config.ts');
    const pluginFile = path.join(root, 'append-plugin.ts');
    await fs.writeFile(pluginFile, `
      import type { Plugin } from '${path.resolve(__dirname, '../src/plugin').replaceAll('\\', '/')}';
      export const appendPlugin: Plugin = {
        onFile(page) { page.html += '<footer>Configured</footer>'; }
      };
    `);
    await fs.writeFile(configFile, `
      import { appendPlugin } from './append-plugin';
      export default { plugins: [appendPlugin] };
    `);

    await buildSite({ contentDir, outputDir, configFile });

    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8'))
      .resolves.toContain('<footer>Configured</footer>');
  });
});
