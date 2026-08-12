import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';

import { PluginPipeline, type Plugin, type PluginContext } from '../src/plugin';
import { SSGEngine, loadConfig } from '../src/engine';
import { build } from '../src/ssg';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/templates';
import type { Page } from '../src/types';

const FIXTURES = path.join(__dirname, 'fixtures');
const CONTENT_DIR = path.join(FIXTURES, 'content');

describe('PluginPipeline', () => {
  it('runs every lifecycle hook across all plugins in registration order', async () => {
    const order: string[] = [];
    const makePlugin = (name: string): Plugin => ({
      name,
      onStart: () => {
        order.push(`${name}:start`);
      },
      beforeBuild: () => {
        order.push(`${name}:before`);
      },
      onFile: () => {
        order.push(`${name}:file`);
      },
      afterBuild: () => {
        order.push(`${name}:after`);
      },
      onEnd: () => {
        order.push(`${name}:end`);
      },
    });
    const pipeline = new PluginPipeline();
    pipeline.use(makePlugin('a')).use(makePlugin('b'));
    const ctx: PluginContext = {
      options: { contentDir: '', outputDir: '' },
      pages: [],
      outputs: new Map(),
      shared: new Map(),
    };
    await pipeline.runStart(ctx);
    await pipeline.runBeforeBuild(ctx);
    await pipeline.runOnFile(
      { slug: 'x', title: 'X', tags: [], content: '', html: '' },
      ctx
    );
    await pipeline.runAfterBuild(ctx);
    await pipeline.runOnEnd(ctx);
    expect(order).toEqual([
      'a:start',
      'b:start',
      'a:before',
      'b:before',
      'a:file',
      'b:file',
      'a:after',
      'b:after',
      'a:end',
      'b:end',
    ]);
  });

  it('returns registered plugins in order', () => {
    const a: Plugin = { name: 'a' };
    const b: Plugin = { name: 'b' };
    const pipeline = new PluginPipeline([a, b]);
    expect(pipeline.plugins.map((plugin) => plugin.name)).toEqual(['a', 'b']);
  });
});

describe('SSGEngine', () => {
  let tempRoot: string;
  let outputDir: string;

  beforeAll(async () => {
    tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-plugin-test-'));
    outputDir = path.join(tempRoot, 'dist');
  });

  afterAll(async () => {
    await fs.rm(tempRoot, { recursive: true, force: true });
  });

  it('runs a custom plugin onFile hook during a build', async () => {
    const shout: Plugin = {
      name: 'shout',
      onFile(page: Page) {
        page.title = `${page.title}!`;
      },
    };
    const engine = new SSGEngine([new MarkdownPlugin(), shout, new TemplatePlugin()]);
    const pages = await engine.build({ contentDir: CONTENT_DIR, outputDir });
    expect(pages).toHaveLength(2);
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('Fixture One!');
    expect(index).toContain('Fixture Two!');
  });

  it('lets a plugin add extra outputs via afterBuild', async () => {
    const extra: Plugin = {
      name: 'extra',
      afterBuild(ctx: PluginContext) {
        ctx.outputs.set('robots.txt', 'User-agent: *\nDisallow:\n');
      },
    };
    const engine = new SSGEngine([new MarkdownPlugin(), new TemplatePlugin(), extra]);
    await engine.build({ contentDir: CONTENT_DIR, outputDir });
    const robots = await fs.readFile(path.join(outputDir, 'robots.txt'), 'utf8');
    expect(robots).toContain('Disallow');
  });

  it('allows plugins to be passed directly through build options', async () => {
    const pages = await build({
      contentDir: CONTENT_DIR,
      outputDir,
      plugins: [new MarkdownPlugin(), new TemplatePlugin()],
    });
    expect(pages).toHaveLength(2);
  });
});

describe('loadConfig', () => {
  it('loads plugins from a config file', async () => {
    const config = await loadConfig(path.join(FIXTURES, 'config', 'ssg.config'));
    expect(config).not.toBeNull();
    expect(config!.plugins).toBeDefined();
    const names = config!.plugins!.map((plugin) => plugin.name);
    expect(names).toEqual(expect.arrayContaining(['markdown', 'templates', 'dev-server']));
  });

  it('returns null for a missing config file', async () => {
    const config = await loadConfig(path.join(FIXTURES, 'does-not-exist'));
    expect(config).toBeNull();
  });
});
