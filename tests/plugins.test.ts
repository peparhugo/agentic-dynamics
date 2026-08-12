import fs from 'fs';
import os from 'os';
import path from 'path';
import { PluginPipeline } from '../src/plugin';
import type { Page, Plugin, PluginContext } from '../src/types';
import { SSGEngine } from '../src/engine';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/template';
import { DevServerPlugin } from '../src/plugins/dev-server';
import { loadConfig, loadPluginsFromConfig, toPlugin } from '../src/plugin-loader';
import { readPages, sortPages } from '../src/markdown';
import { build } from '../src/ssg';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-'));
}

function makeCtx(overrides: Partial<PluginContext> = {}): PluginContext {
  return {
    config: { plugins: [] },
    contentDir: './content',
    outputDir: './dist',
    templatesDir: './templates',
    pages: [],
    templates: {
      dir: './templates',
      templates: new Map(),
      layouts: new Map(),
      partials: new Map(),
    },
    output: {},
    ...overrides,
  };
}

function writeConfig(dir: string, pluginName: string): string {
  fs.mkdirSync(path.join(dir, 'plugins'));
  fs.writeFileSync(
    path.join(dir, 'plugins', `${pluginName}.ts`),
    `// @ts-nocheck
import type { Plugin, PluginContext } from '../../../src/types';
export default class ${pluginName} implements Plugin {
  readonly name = 'spy';
  onStart(ctx: PluginContext): void { ctx.output.spyRan = true; }
}`
  );
  const configPath = path.join(dir, 'ssg.config.ts');
  fs.writeFileSync(
    configPath,
    `// @ts-nocheck
import type { SSGConfig } from '../../src/types';
const config: SSGConfig = { plugins: ['./plugins/${pluginName}'] };
export default config;`
  );
  return configPath;
}

describe('PluginPipeline', () => {
  it('runs each hook across all plugins in registration order', () => {
    const order: string[] = [];
    const make = (name: string): Plugin => ({
      name,
      onStart: () => {
        order.push(`${name}:onStart`);
      },
      beforeBuild: () => {
        order.push(`${name}:beforeBuild`);
      },
      afterBuild: () => {
        order.push(`${name}:afterBuild`);
      },
      onFile: () => {
        order.push(`${name}:onFile`);
      },
      onEnd: () => {
        order.push(`${name}:onEnd`);
      },
    });

    const pipeline = new PluginPipeline();
    pipeline.add(make('a'));
    pipeline.add(make('b'));
    const ctx = makeCtx();

    pipeline.onStart(ctx);
    pipeline.beforeBuild(ctx);
    pipeline.onFile({} as Page, ctx);
    pipeline.afterBuild(ctx);
    pipeline.onEnd(ctx);

    expect(order).toEqual([
      'a:onStart',
      'b:onStart',
      'a:beforeBuild',
      'b:beforeBuild',
      'a:onFile',
      'b:onFile',
      'a:afterBuild',
      'b:afterBuild',
      'a:onEnd',
      'b:onEnd',
    ]);
  });

  it('skips hooks that a plugin does not implement', () => {
    const pipeline = new PluginPipeline();
    pipeline.add({ name: 'quiet' });
    expect(() => pipeline.onStart(makeCtx())).not.toThrow();
    expect(pipeline.size).toBe(1);
  });
});

describe('built-in plugins', () => {
  it('MarkdownPlugin parses content into pages during beforeBuild', () => {
    const content = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      const ctx = makeCtx({ contentDir: content });
      new MarkdownPlugin().beforeBuild(ctx);
      expect(ctx.pages).toHaveLength(1);
      expect(ctx.pages[0].slug).toBe('a');
      expect(ctx.pages[0].title).toBe('A');
      expect(ctx.pages[0].html).toContain('<h1>A</h1>');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
    }
  });

  it('TemplatePlugin renders pages and the index through templates', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(templates, 'default.hbs'), 'TPL {{title}}\n{{{html}}}');
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');

      const ctx = makeCtx({ contentDir: content, outputDir: output, templatesDir: templates });
      ctx.pages = sortPages(readPages(content));

      const plugin = new TemplatePlugin();
      plugin.beforeBuild(ctx);
      plugin.onFile(ctx.pages[0], ctx);
      plugin.afterBuild(ctx);

      expect(fs.readFileSync(path.join(output, 'a.html'), 'utf8')).toContain('TPL A');
      expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('DevServerPlugin injects the live reload script', () => {
    const plugin = new DevServerPlugin();
    const html = '<!DOCTYPE html><html><body><h1>Hi</h1></body></html>';
    const out = plugin.injectLiveReload(html, 3000);
    expect(out).toContain('ssg-live-reload');
    expect(out).toContain('var port = 3000');
    expect(out).toContain('/live-reload');
    expect(out.indexOf('ssg-live-reload')).toBeLessThan(out.indexOf('</body>'));
  });
});

describe('plugin loading from config', () => {
  it('loads the default config file from the working directory', () => {
    expect(fs.existsSync(path.resolve('ssg.config.ts'))).toBe(true);
    const config = loadConfig();
    expect(Array.isArray(config.plugins)).toBe(true);
  });

  it('loads a config file and instantiates its plugins', () => {
    const dir = makeTempDir();
    try {
      const configPath = writeConfig(dir, 'Spy');
      const config = loadConfig(configPath);
      expect(config.plugins).toEqual(['./plugins/Spy']);

      const plugins = loadPluginsFromConfig(config, dir);
      expect(plugins).toHaveLength(1);
      expect(plugins[0].name).toBe('spy');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('returns an empty config when none exists', () => {
    const config = loadConfig(path.join(os.tmpdir(), 'no-config-xyz'));
    expect(config.plugins).toEqual([]);
  });

  it('normalizes default and named plugin exports', () => {
    const plugin = toPlugin({ default: { name: 'named', onStart() {} } });
    expect(plugin?.name).toBe('named');
  });
});

describe('SSGEngine', () => {
  it('orchestrates the pipeline and runs config plugins', () => {
    const dir = makeTempDir();
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      const configPath = writeConfig(dir, 'Spy');

      const engine = new SSGEngine({
        contentDir: content,
        outputDir: output,
        templatesDir: templates,
        configPath,
      });

      expect(engine.pipeline.size).toBe(4);
      const pages = engine.build();

      expect(pages.map((p) => p.slug)).toEqual(['a']);
      expect(engine.context.output.spyRan).toBe(true);
      expect(fs.existsSync(path.join(output, 'a.html'))).toBe(true);
      expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('build() keeps producing the same output as before the refactor', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'post.md'), '<!--\ntitle: Post\ntags: [news]\n-->\n# Post body');
      const pages = build(content, output);
      expect(pages).toHaveLength(1);
      const html = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
      expect(html).toContain('<title>Post</title>');
      expect(html).toContain('<h1>Post body</h1>');
      expect(html).toContain('Tags:');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
    }
  });
});
