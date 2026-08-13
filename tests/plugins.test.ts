import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type Plugin } from '../src';

describe('plugin pipeline', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugins-'));
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('runs every lifecycle hook for all plugins in order', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const calls: string[] = [];
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# Page');

    const plugin = (name: string): Plugin => ({
      onStart: async () => { calls.push(`${name}:start`); },
      beforeBuild: () => { calls.push(`${name}:before`); },
      onFile: (page) => {
        calls.push(`${name}:file`);
        page.html = `${page.html}<span>${name}</span>`;
      },
      afterBuild: () => { calls.push(`${name}:after`); },
      onEnd: () => { calls.push(`${name}:end`); },
    });

    await buildSite({ contentDir: content, outputDir: output, plugins: [plugin('one'), plugin('two')] });

    expect(calls).toEqual([
      'one:start', 'two:start',
      'one:before', 'two:before',
      'one:file', 'two:file',
      'one:after', 'two:after',
      'one:end', 'two:end',
    ]);
    await expect(fs.readFile(path.join(output, 'page.html'), 'utf8'))
      .resolves.toContain('<span>one</span><span>two</span>');
  });

  test('loads TypeScript plugins from ssg.config.ts', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const plugins = path.join(root, 'plugins');
    await fs.mkdir(content);
    await fs.mkdir(plugins);
    await fs.writeFile(path.join(content, 'page.md'), 'Configured');
    await fs.writeFile(path.join(plugins, 'suffix.ts'), `
import type { Plugin } from '${path.resolve(__dirname, '../src').replaceAll('\\', '/')}';
const plugin: Plugin = { onFile(page) { page.html += '<footer>plugin</footer>'; } };
export default plugin;
`);
    await fs.writeFile(path.join(root, 'ssg.config.ts'), `
import suffix from './plugins/suffix';
export default { plugins: [suffix] };
`);

    await buildSite({
      contentDir: content,
      outputDir: output,
      configFile: path.join(root, 'ssg.config.ts'),
    });

    await expect(fs.readFile(path.join(output, 'page.html'), 'utf8'))
      .resolves.toContain('<footer>plugin</footer>');
  });

  test('always runs onEnd when a build hook fails', async () => {
    const content = path.join(root, 'content');
    const ended = jest.fn();
    await fs.mkdir(content);

    await expect(buildSite({
      contentDir: content,
      outputDir: path.join(root, 'dist'),
      plugins: [{ beforeBuild() { throw new Error('stop'); }, onEnd: ended }],
    })).rejects.toThrow('stop');
    expect(ended).toHaveBeenCalledTimes(1);
  });
});
