import fs from 'fs';
import os from 'os';
import path from 'path';

import { loadConfig, loadPlugins, resolveConfigPath, resolvePluginSpec } from '../config';
import { MarkdownPlugin, MARKDOWN_PLUGIN_NAME } from '../plugins/markdown';
import { TemplatePlugin, TEMPLATE_PLUGIN_NAME } from '../plugins/template';
import type { Plugin } from '../plugin';

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

describe('resolveConfigPath', () => {
  it('defaults to ./ssg.config.ts in the working directory', () => {
    expect(resolveConfigPath()).toBe(path.resolve('ssg.config.ts'));
  });

  it('resolves an explicit path', () => {
    expect(resolveConfigPath('configs/my.ts')).toBe(path.resolve('configs/my.ts'));
  });
});

describe('loadConfig', () => {
  it('returns an empty config when no config file exists', () => {
    const loaded = loadConfig(path.join(os.tmpdir(), 'missing-ssg-config.ts'));
    expect(loaded.config).toEqual({});
    expect(loaded.dir).toBe(path.dirname(path.resolve(path.join(os.tmpdir(), 'missing-ssg-config.ts'))));
  });

  it('loads a config file with a plugins array', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-config-'));
    writeTree(dir, {
      'ssg.config.ts': `export default { plugins: ['./plugins/custom'] };`,
      'plugins/custom.ts': `const plugin = { name: 'custom', onStart: () => {} };\nexport default plugin;`,
    });

    try {
      const loaded = loadConfig(path.join(dir, 'ssg.config.ts'));
      expect(loaded.config.plugins).toEqual(['./plugins/custom']);
      expect(loaded.dir).toBe(dir);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('resolvePluginSpec', () => {
  it('resolves built-in plugin names', () => {
    expect(resolvePluginSpec('markdown', process.cwd()).name).toBe(MARKDOWN_PLUGIN_NAME);
    expect(resolvePluginSpec('templates', process.cwd()).name).toBe(TEMPLATE_PLUGIN_NAME);
  });

  it('resolves a plugin object directly', () => {
    const plugin: Plugin = { name: 'inline' };
    expect(resolvePluginSpec(plugin, process.cwd())).toBe(plugin);
  });

  it('resolves a plugin factory function', () => {
    const factory = (): Plugin => ({ name: 'made' });
    expect(resolvePluginSpec(factory, process.cwd()).name).toBe('made');
  });

  it('loads a TypeScript plugin module relative to the base directory', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-'));
    writeTree(dir, {
      'plugins/my-plugin.ts': `const plugin = { name: 'my-plugin' };\nexport default plugin;`,
    });

    try {
      expect(resolvePluginSpec('./plugins/my-plugin', dir).name).toBe('my-plugin');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('throws for an unresolvable plugin module', () => {
    expect(() => resolvePluginSpec('./plugins/nope', os.tmpdir())).toThrow(/not found/);
  });
});

describe('loadPlugins', () => {
  it('always includes the built-in markdown and template plugins', () => {
    const plugins = loadPlugins(loadConfig(path.join(os.tmpdir(), 'missing-config.ts')));
    const names = plugins.map((plugin) => plugin.name);
    expect(names).toContain(MARKDOWN_PLUGIN_NAME);
    expect(names).toContain(TEMPLATE_PLUGIN_NAME);
  });

  it('appends config plugins after the built-ins', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugins-'));
    writeTree(dir, {
      'plugins/extra.ts': `const plugin = { name: 'extra' };\nexport default plugin;`,
    });

    try {
      const loaded = loadConfig(path.join(dir, 'ssg.config.ts'));
      loaded.config.plugins = ['./plugins/extra'];
      const plugins = loadPlugins(loaded);
      expect(plugins.map((plugin) => plugin.name)).toEqual([
        MARKDOWN_PLUGIN_NAME,
        TEMPLATE_PLUGIN_NAME,
        'extra',
      ]);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('appends options.plugins after the config plugins', () => {
    const extra: Plugin = { name: 'manual' };
    const plugins = loadPlugins(loadConfig(path.join(os.tmpdir(), 'missing-config.ts')), {
      contentDir: 'content',
      outputDir: 'dist',
      plugins: [extra],
    });
    expect(plugins[plugins.length - 1]).toBe(extra);
    expect(plugins[0]).toBeInstanceOf(MarkdownPlugin);
    expect(plugins[1]).toBeInstanceOf(TemplatePlugin);
  });
});
