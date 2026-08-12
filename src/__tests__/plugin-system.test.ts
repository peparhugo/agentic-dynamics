import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { buildSite, createEngine } from '../build';
import { loadConfiguredPlugins } from '../config';
import { Plugin } from '../plugin';
import { defaultPlugins, MarkdownPlugin, TemplatePlugin, DevServerPlugin } from '../plugins';
import { Page } from '../types';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugin-'));
}

async function write(filePath: string, content: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, 'utf-8');
}

describe('plugin interface', () => {
  it('exposes the built-in plugins with the expected hooks', () => {
    const markdown = new MarkdownPlugin();
    const template = new TemplatePlugin();
    const dev = new DevServerPlugin({ contentDir: './c', outputDir: './o' });
    expect(markdown.name).toBe('markdown');
    expect(typeof markdown.onFile).toBe('function');
    expect(template.name).toBe('template');
    expect(typeof template.beforeBuild).toBe('function');
    expect(typeof template.onFile).toBe('function');
    expect(dev.name).toBe('dev-server');
    expect(typeof dev.onStart).toBe('function');
    expect(typeof dev.afterBuild).toBe('function');
    expect(typeof dev.onEnd).toBe('function');
  });

  it('defaultPlugins returns markdown and template in order', () => {
    const plugins = defaultPlugins();
    expect(plugins.map((p) => p.name)).toEqual(['markdown', 'template']);
  });
});

describe('pipeline ordering', () => {
  it('runs onFile hooks in registration order and transforms the rendered output', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await write(path.join(contentDir, 'a.md'), '# A\n\nHello');

    const order: string[] = [];
    const record = (name: string): Plugin => ({
      name,
      onFile(page: Page) {
        order.push(name);
        if (name === 'aaa') {
          expect(page.html).toContain('<h1>A</h1>');
          expect(typeof page.renderedHtml).toBe('string');
        }
        page.renderedHtml = (page.renderedHtml ?? '') + `<p>${name}</p>`;
        return page;
      },
    });
    const pluginA = record('aaa');
    const pluginB = record('bbb');

    const engine = createEngine({ contentDir, outputDir }, [pluginA, pluginB]);
    await engine.start();
    await engine.build();
    await engine.close();

    expect(order).toEqual(['aaa', 'bbb']);
    expect(
      await fs.readFile(path.join(outputDir, 'a.html'), 'utf-8')
    ).toContain('<p>aaa</p><p>bbb</p>');
  });

  it('runs start/end hooks around builds', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await write(path.join(contentDir, 'a.md'), '# A');

    const log: string[] = [];
    const plugin: Plugin = {
      name: 'logger',
      onStart() {
        log.push('start');
      },
      beforeBuild() {
        log.push('beforeBuild');
      },
      afterBuild() {
        log.push('afterBuild');
      },
      onEnd() {
        log.push('end');
      },
    };

    const engine = createEngine({ contentDir, outputDir }, [plugin]);
    await engine.start();
    await engine.build();
    await engine.build();
    await engine.close();

    expect(log).toEqual([
      'start',
      'beforeBuild',
      'afterBuild',
      'beforeBuild',
      'afterBuild',
      'end',
    ]);
  });
});

describe('config loading', () => {
  it('loads plugins referenced from ssg.config.ts', async () => {
    const root = await makeTempDir();
    await write(
      path.join(root, 'plugins', 'yell.ts'),
      `
const plugin = {
  name: 'yell',
  onFile: (page: { html: string }) => {
    page.html = page.html.toUpperCase();
    return page;
  },
};
export default plugin;
`
    );
    await write(
      path.join(root, 'ssg.config.ts'),
      `import yell from './plugins/yell';\nexport default { plugins: [yell] };\n`
    );

    const { plugins, config } = await loadConfiguredPlugins(root);
    expect(config.plugins?.length).toBe(1);
    expect(plugins.map((p) => p.name)).toEqual(['yell']);
  });

  it('loads plugins from ssg.config.js and merges them into buildSite', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await write(path.join(contentDir, 'a.md'), '# A\n\nHello');

    await write(
      path.join(root, 'ssg.config.js'),
      `module.exports = { plugins: [{ name: 'suffix', onFile: (page) => { page.renderedHtml = (page.renderedHtml ?? '') + '<p>SUFFIX</p>'; return page; } }] };`
    );

    const previousCwd = process.cwd();
    process.chdir(root);
    try {
      await buildSite({ contentDir, outputDir });

      const html = await fs.readFile(path.join(outputDir, 'a.html'), 'utf-8');
      expect(html).toContain('<p>SUFFIX</p>');
    } finally {
      process.chdir(previousCwd);
    }
  });

  it('returns empty config when no config file exists', async () => {
    const root = await makeTempDir();
    const { plugins, config } = await loadConfiguredPlugins(root);
    expect(config).toEqual({});
    expect(plugins).toEqual([]);
  });
});
