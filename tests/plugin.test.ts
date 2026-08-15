import fs from 'fs';
import os from 'os';
import path from 'path';
import { SSGEngine } from '../src/engine';
import { PluginContext, Plugin } from '../src/plugin';
import { loadConfig } from '../src/config';
import { markdownPlugin } from '../plugins/markdown-plugin';
import { templatePlugin } from '../plugins/template-plugin';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('plugin pipeline', () => {
  let contentDir: string;
  let templatesDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-plugin-content-');
    templatesDir = makeTmpDir('ssg-plugin-templates-');
    outputDir = makeTmpDir('ssg-plugin-dist-');
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body><h2>{{title}}</h2>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      `---\ntitle: Hello\n---\n# Hi\n\nSome **text**.`
    );
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('runs each lifecycle hook for every plugin, in plugin order', () => {
    const calls: string[] = [];
    const pluginA: Plugin = {
      name: 'a',
      beforeBuild: () => calls.push('a:beforeBuild'),
      onFile: (page) => calls.push(`a:onFile:${page.slug}`),
      afterBuild: () => calls.push('a:afterBuild'),
    };
    const pluginB: Plugin = {
      name: 'b',
      beforeBuild: () => calls.push('b:beforeBuild'),
      onFile: (page) => calls.push(`b:onFile:${page.slug}`),
      afterBuild: () => calls.push('b:afterBuild'),
    };

    const engine = new SSGEngine([pluginA, pluginB]);
    const ctx: PluginContext = { contentDir, outputDir, templatesDir };
    engine.runBuild(ctx);

    expect(calls).toEqual([
      'a:beforeBuild',
      'b:beforeBuild',
      'a:onFile:hello',
      'b:onFile:hello',
      'a:afterBuild',
      'b:afterBuild',
    ]);
  });

  it('lets a plugin transform the page draft that later plugins and the final Page see', () => {
    const upperCasePlugin: Plugin = {
      name: 'uppercase-title',
      onFile: (page) => {
        page.title = page.title.toUpperCase();
      },
    };
    const engine = new SSGEngine([upperCasePlugin, markdownPlugin(), templatePlugin()]);
    const ctx: PluginContext = { contentDir, outputDir, templatesDir };
    const page = engine.buildFile(contentDir, 'hello.md', ctx);

    expect(page.title).toBe('HELLO');
    expect(page.html).toContain('<h2>HELLO</h2>');
    expect(page.html).toContain('<h1>Hi</h1>');
  });

  it('reproduces the built-in markdown+template output equivalent to the original single-pass build', () => {
    const engine = new SSGEngine([markdownPlugin(), templatePlugin()]);
    const ctx: PluginContext = { contentDir, outputDir, templatesDir };
    const page = engine.buildFile(contentDir, 'hello.md', ctx);

    expect(page.title).toBe('Hello');
    expect(page.html).toContain('<h1>Hi</h1>');
    expect(page.html).toContain('<strong>text</strong>');
  });

  it('falls back to the built-in markdown + template plugins when no ssg.config.ts is present', () => {
    const projectDir = makeTmpDir('ssg-plugin-noconfig-');
    const config = loadConfig(projectDir);
    expect(config.plugins.map((p) => p.name)).toEqual(['markdown', 'template']);
    fs.rmSync(projectDir, { recursive: true, force: true });
  });
});
