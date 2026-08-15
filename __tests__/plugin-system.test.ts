import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/generator';
import { loadConfig } from '../src/config';

describe('plugin system integration', () => {
  it('loads a custom plugin from ssg.config.ts and runs its hooks in order', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugin-test-'));
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(path.join(contentDir, 'hello.md'), '# Hello', 'utf8');

    const pluginsDir = path.join(root, 'plugins');
    await fs.mkdir(pluginsDir, { recursive: true });
    await fs.writeFile(
      path.join(pluginsDir, 'my-plugin.ts'),
      [
        'import { Plugin, PluginContext } from "../src/plugin";',
        'import { Page } from "../src/types";',
        'export default class MyPlugin implements Plugin {',
        '  readonly name = "my-plugin";',
        '  readonly events: string[] = [];',
        '  async onStart(_ctx: PluginContext) { this.events.push("onStart"); }',
        '  async beforeBuild(_ctx: PluginContext) { this.events.push("beforeBuild"); }',
        '  async onFile(page: Page, _ctx: PluginContext) { this.events.push("onFile:" + page.slug); }',
        '  async afterBuild(ctx: PluginContext) { this.events.push("afterBuild"); ctx.outputFiles.set("plugin.txt", this.events.join("|")); }',
        '  async onEnd(ctx: PluginContext) { this.events.push("onEnd"); ctx.outputFiles.set("onend.txt", this.events.join("|")); }',
        '}',
      ].join('\n'),
      'utf8'
    );

    await fs.writeFile(
      path.join(root, 'ssg.config.ts'),
      [
        'import type { SsgConfig } from "./src/plugin";',
        'const config: SsgConfig = { plugins: ["my-plugin"] };',
        'export default config;',
      ].join('\n'),
      'utf8'
    );

    const cwd = process.cwd();
    process.chdir(root);
    try {
      const config = await loadConfig();
      expect(config.plugins).toEqual(['my-plugin']);

      const pages = await build({ contentDir, outputDir, templatesDir: path.join(root, 'templates') });
      expect(pages).toHaveLength(1);
      expect(pages[0].slug).toBe('hello');

      const pluginTxt = await fs.readFile(path.join(outputDir, 'plugin.txt'), 'utf8');
      expect(pluginTxt.split('|')[0]).toBe('onStart');
      expect(pluginTxt).toContain('beforeBuild');
      expect(pluginTxt).toContain('onFile:hello');
      expect(pluginTxt).toContain('afterBuild');

      const onEndTxt = await fs.readFile(path.join(outputDir, 'onend.txt'), 'utf8');
      expect(onEndTxt).toContain('onEnd');
      expect(onEndTxt.indexOf('onEnd')).toBeGreaterThan(onEndTxt.indexOf('afterBuild'));
    } finally {
      process.chdir(cwd);
    }
  });
});
