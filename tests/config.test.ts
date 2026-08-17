import fs from 'fs';
import { promises as fsp } from 'fs';
import os from 'os';
import path from 'path';
import { loadConfig, loadPlugin } from '../src/config';
import { buildSite } from '../src/generate';
import type { Plugin } from '../src/plugin';

async function makeTempDir(): Promise<string> {
  return fsp.mkdtemp(path.join(os.tmpdir(), 'ssg-config-test-'));
}

describe('loadConfig', () => {
  it('discovers a json config file in the given directory', async () => {
    const dir = await makeTempDir();
    await fsp.writeFile(path.join(dir, 'ssg.config.json'), JSON.stringify({ plugins: [] }));

    const config = await loadConfig(dir);
    expect(config).toEqual({ plugins: [] });
  });

  it('returns an empty config when none is present', async () => {
    const dir = await makeTempDir();
    const config = await loadConfig(dir);
    expect(config).toEqual({});
  });
});

describe('loadPlugin', () => {
  it('loads a plugin object from a CommonJS module', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-test-'));
    fs.writeFileSync(
      path.join(dir, 'my-plugin.js'),
      'module.exports = { name: "tagger", onFile() {} };\n'
    );

    const plugin = loadPlugin('./my-plugin.js', dir);
    expect(plugin.name).toBe('tagger');
  });

  it('instantiates a plugin factory exported from a module', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-test-'));
    fs.writeFileSync(
      path.join(dir, 'factory.js'),
      'module.exports = () => ({ name: "factory", onStart() {} });\n'
    );

    const plugin = loadPlugin('./factory.js', dir);
    expect(plugin.name).toBe('factory');
  });

  it('returns a plugin object unchanged', () => {
    const plugin: Plugin = { name: 'inline', onEnd: () => undefined };
    expect(loadPlugin(plugin)).toBe(plugin);
  });
});

describe('buildSite with plugin options', () => {
  it('runs user plugins supplied directly', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();

    await fsp.writeFile(path.join(content, 'a.md'), '# Hello\n');

    const touched: string[] = [];
    const plugin: Plugin = {
      name: 'tagger',
      onStart: () => {
        touched.push('start');
      },
      onFile(page) {
        touched.push(`file:${page.slug}`);
        page.tags.push('from-plugin');
      },
      onEnd: () => {
        touched.push('end');
      },
    };

    const result = await buildSite(content, output, undefined, { plugins: [plugin] });

    expect(result.pages[0].tags).toContain('from-plugin');
    expect(touched).toContain('start');
    expect(touched).toContain('file:a');
    expect(touched).toContain('end');

    const html = await fsp.readFile(path.join(output, 'a.html'), 'utf8');
    expect(html).toContain('from-plugin');
  });
});
