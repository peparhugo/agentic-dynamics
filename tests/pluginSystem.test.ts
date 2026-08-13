import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { loadConfig } from '../src/config';
import { SSGEngine } from '../src/engine';
import { buildSite } from '../src/generator';
import { Plugin, PluginContext } from '../src/plugin';
import { createDevServerPlugin } from '../src/plugins/devServerPlugin';
import { createMarkdownPlugin } from '../src/plugins/markdownPlugin';
import { createTemplatePlugin } from '../src/plugins/templatePlugin';
import { DevServer } from '../src/devServer';

function makeTmpDir(prefix = 'ssg-plugin-test-'): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function recordingPlugin(name: string, log: string[]): Plugin {
  return {
    name,
    onStart: () => {
      log.push(`${name}:onStart`);
    },
    beforeBuild: () => {
      log.push(`${name}:beforeBuild`);
    },
    onFile: (page) => {
      log.push(`${name}:onFile:${page.slug}`);
    },
    afterBuild: () => {
      log.push(`${name}:afterBuild`);
    },
    onEnd: () => {
      log.push(`${name}:onEnd`);
    },
  };
}

describe('SSGEngine.runSync', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: a\n---\nBody A');
    fs.writeFileSync(path.join(contentDir, 'b.md'), '---\ntitle: b\n---\nBody B');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('runs every plugin hook for a stage, in plugin order, before moving to the next stage', () => {
    const log: string[] = [];
    const engine = new SSGEngine([
      createMarkdownPlugin(),
      recordingPlugin('first', log),
      recordingPlugin('second', log),
    ]);

    engine.runSync({ contentDir, outputDir });

    // onStart: all plugins, in order. beforeBuild: all plugins, in order (markdown loads pages).
    expect(log.slice(0, 2)).toEqual(['first:onStart', 'second:onStart']);
    expect(log.slice(2, 4)).toEqual(['first:beforeBuild', 'second:beforeBuild']);

    // onFile: for each page, the full chain runs before moving to the next page.
    const onFileEvents = log.filter((e) => e.includes(':onFile:'));
    expect(onFileEvents).toEqual(['first:onFile:a', 'second:onFile:a', 'first:onFile:b', 'second:onFile:b']);

    expect(log.slice(-4)).toEqual(['first:afterBuild', 'second:afterBuild', 'first:onEnd', 'second:onEnd']);
  });

  it('lets an onFile plugin transform a page before a later plugin persists it', () => {
    const upper: Plugin = {
      name: 'upper',
      onFile: (page) => ({ ...page, title: page.title.toUpperCase() }),
    };
    const engine = new SSGEngine([createMarkdownPlugin(), upper, createTemplatePlugin()]);

    const result = engine.runSync({ contentDir, outputDir });

    expect(result.pages.map((p) => p.title).sort()).toEqual(['A', 'B']);
    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8');
    expect(html).toContain('<h1>A</h1>');
  });

  it('throws a clear error when a plugin hook is async', () => {
    const asyncPlugin: Plugin = {
      name: 'bad-async',
      onStart: async () => {
        await Promise.resolve();
      },
    };
    const engine = new SSGEngine([asyncPlugin]);

    expect(() => engine.runSync({ contentDir, outputDir })).toThrow(/bad-async.*onStart.*SSGEngine\.run/);
  });

  it('propagates the missing content-directory error from MarkdownPlugin', () => {
    const engine = new SSGEngine([createMarkdownPlugin(), createTemplatePlugin()]);
    expect(() => engine.runSync({ contentDir: path.join(contentDir, 'missing'), outputDir })).toThrow(
      /Content directory not found/
    );
  });
});

describe('SSGEngine.run (async)', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\nBody A');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('awaits async plugin hooks in order across stages', async () => {
    const log: string[] = [];
    const asyncPlugin: Plugin = {
      name: 'delayed',
      onStart: async () => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        log.push('delayed:onStart');
      },
      onFile: async (page) => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        log.push(`delayed:onFile:${page.slug}`);
      },
    };
    const engine = new SSGEngine([createMarkdownPlugin(), asyncPlugin, createTemplatePlugin()]);

    const result = await engine.run({ contentDir, outputDir });

    expect(log).toEqual(['delayed:onStart', 'delayed:onFile:a']);
    expect(result.pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
  });

  it('produces the same build output as buildSite() for the built-in plugin pair', async () => {
    const asyncOutputDir = makeTmpDir();
    const engine = new SSGEngine([createMarkdownPlugin(), createTemplatePlugin()]);
    const asyncResult = await engine.run({ contentDir, outputDir: asyncOutputDir });
    const syncResult = buildSite({ contentDir, outputDir });

    expect(asyncResult.pages.map((p) => p.title)).toEqual(syncResult.pages.map((p) => p.title));
    expect(fs.readFileSync(path.join(asyncOutputDir, 'a.html'), 'utf-8')).toBe(
      fs.readFileSync(path.join(outputDir, 'a.html'), 'utf-8')
    );

    fs.rmSync(asyncOutputDir, { recursive: true, force: true });
  });
});

describe('createDevServerPlugin', () => {
  let contentDir: string;
  let outputDir: string;
  let server: DevServer | undefined;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\nBody A');
  });

  afterEach(async () => {
    if (server) {
      await server.close();
      server = undefined;
    }
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('starts a dev server as the final stage of an async pipeline', async () => {
    const devServerPlugin = createDevServerPlugin({
      port: 0,
      onServerStart: (s) => {
        server = s;
      },
    });
    const engine = new SSGEngine([createMarkdownPlugin(), createTemplatePlugin(), devServerPlugin]);

    await engine.run({ contentDir, outputDir });

    expect(server).toBeDefined();
    const res = await fetch(`http://localhost:${server!.port}/a.html`);
    expect(res.status).toBe(200);
  });
});

describe('loadConfig', () => {
  let configDir: string;

  beforeEach(() => {
    configDir = makeTmpDir('ssg-config-test-');
  });

  afterEach(() => {
    fs.rmSync(configDir, { recursive: true, force: true });
  });

  it('returns an empty plugin list when the config file does not exist', () => {
    const config = loadConfig(path.join(configDir, 'missing.config.ts'));
    expect(config).toEqual({ plugins: [] });
  });

  it('loads plugins and directories from a TypeScript config module with a default export', () => {
    const configPath = path.join(configDir, 'ssg.config.ts');
    fs.writeFileSync(
      configPath,
      `
      const config = {
        plugins: [{ name: 'noop' }],
        contentDir: './content',
        outputDir: './out',
        templatesDir: './tpl',
      };
      export default config;
      `
    );

    const config = loadConfig(configPath);

    expect(config.plugins).toHaveLength(1);
    expect(config.plugins[0].name).toBe('noop');
    expect(config.contentDir).toBe('./content');
    expect(config.outputDir).toBe('./out');
    expect(config.templatesDir).toBe('./tpl');
  });

  it('loads plugins from a CommonJS-style module.exports config', () => {
    const configPath = path.join(configDir, 'ssg.config.js');
    fs.writeFileSync(
      configPath,
      `module.exports = { plugins: [{ name: 'cjs-plugin' }] };`
    );

    const config = loadConfig(configPath);

    expect(config.plugins.map((p) => p.name)).toEqual(['cjs-plugin']);
  });
});
