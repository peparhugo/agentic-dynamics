import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';
import { createBuiltInPlugins, loadPlugins } from '../src/config';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/template';
import { DevServerPlugin } from '../src/plugins/dev-server';
import type { Plugin } from '../src/plugin';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-'));
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('plugin system', () => {
  it('loads the built-in plugins in order', () => {
    const plugins = createBuiltInPlugins();
    expect(plugins.map((p) => p.name)).toEqual(['markdown', 'template', 'dev-server']);
    expect(plugins[0]).toBeInstanceOf(MarkdownPlugin);
    expect(plugins[1]).toBeInstanceOf(TemplatePlugin);
    expect(plugins[2]).toBeInstanceOf(DevServerPlugin);
  });

  it('runs the full plugin pipeline in order', () => {
    const contentDir = makeTempDir();
    const outputDir = path.join(makeTempDir(), 'dist');
    writeFile(contentDir, 'a.md', '---\ntitle: A\n---\nBody a');
    writeFile(contentDir, 'b.md', '---\ntitle: B\n---\nBody b');

    const events: string[] = [];
    const recorder: Plugin = {
      name: 'recorder',
      onStart: () => events.push('onStart'),
      beforeBuild: () => events.push('beforeBuild'),
      onFile: (page) => events.push(`onFile:${page.slug}`),
      afterBuild: () => events.push('afterBuild'),
      onEnd: () => events.push('onEnd'),
    };

    build({ contentDir, outputDir, plugins: [recorder] });

    expect(events).toEqual([
      'onStart',
      'beforeBuild',
      'onFile:a',
      'onFile:b',
      'afterBuild',
      'onEnd',
    ]);

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(path.dirname(outputDir), { recursive: true, force: true });
  });

  it('lets a custom plugin transform the rendered output', () => {
    const contentDir = makeTempDir();
    const outputDir = path.join(makeTempDir(), 'dist');
    writeFile(contentDir, 'hello.md', '---\ntitle: Hello\n---\nBody text.');

    const banner: Plugin = {
      name: 'banner',
      onFile: (page) => {
        page.html = `<!-- banner -->\n${page.html}`;
      },
    };

    build({ contentDir, outputDir, plugins: [banner] });

    const html = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<!-- banner -->');
    expect(html).toContain('<h1>Hello</h1>');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(path.dirname(outputDir), { recursive: true, force: true });
  });

  it('loads additional plugins from a TypeScript config file', () => {
    const contentDir = makeTempDir();
    const outputDir = path.join(makeTempDir(), 'dist');
    const configPath = path.join(makeTempDir(), 'ssg.config.ts');
    writeFile(contentDir, 'hello.md', '---\ntitle: Hello\n---\nBody.');

    writeFile(
      path.dirname(configPath),
      'ssg.config.ts',
      [
        'export default {',
        '  plugins: [',
        '    {',
        "      name: 'stamp',",
        '      onFile(page: any) {',
        "        page.html = page.html + '\\n<!-- stamped -->';",
        '      },',
        '    },',
        '  ],',
        '};',
        '',
      ].join('\n')
    );

    const plugins = loadPlugins({ contentDir, outputDir, config: configPath });
    expect(plugins.map((p) => p.name)).toEqual(['markdown', 'template', 'dev-server', 'stamp']);

    build({ contentDir, outputDir, config: configPath });

    const html = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<!-- stamped -->');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(path.dirname(outputDir), { recursive: true, force: true });
    fs.rmSync(path.dirname(configPath), { recursive: true, force: true });
  });
});
