import { mkdtempSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { PluginManager, type Plugin, type PluginContext, type PluginFile } from '../src/plugin';
import { SSGEngine } from '../src/engine';
import { buildSite } from '../src/generator';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/templates';
import { DevServerPlugin } from '../src/plugins/dev-server';
import { loadConfig } from '../src/config';

function makeTempDir(): string {
  return mkdtempSync(path.join(tmpdir(), 'ssg-plugin-test-'));
}

function writeFixture(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, content, 'utf8');
  }
}

function makeContext(): PluginContext {
  return {
    contentDir: 'content',
    outputDir: 'dist',
    templatesDir: 'templates',
    port: 3000,
    pages: [],
    files: [],
    options: {},
  };
}

describe('PluginManager', () => {
  it('runs each hook across all plugins in registration order', async () => {
    const calls: string[] = [];
    const pluginA: Plugin = {
      name: 'a',
      onStart: () => {
        calls.push('a:start');
      },
      beforeBuild: () => {
        calls.push('a:before');
      },
      afterBuild: () => {
        calls.push('a:after');
      },
      onFile: () => {
        calls.push('a:file');
      },
      onEnd: () => {
        calls.push('a:end');
      },
    };
    const pluginB: Plugin = {
      name: 'b',
      onStart: () => {
        calls.push('b:start');
      },
      beforeBuild: () => {
        calls.push('b:before');
      },
      afterBuild: () => {
        calls.push('b:after');
      },
      onFile: () => {
        calls.push('b:file');
      },
      onEnd: () => {
        calls.push('b:end');
      },
    };

    const manager = new PluginManager([pluginA, pluginB]);
    const context = makeContext();
    await manager.runHook('onStart', context);
    await manager.runHook('beforeBuild', context);
    await manager.runOnFile(
      { title: '', date: '', tags: [], slug: 'x', source: 'x.md', html: '', raw: '', contentDir: '' },
      context,
    );
    await manager.runHook('afterBuild', context);
    await manager.runHook('onEnd', context);

    expect(calls).toEqual([
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

  it('allows onFile to replace the current page', async () => {
    const plugin: Plugin = {
      name: 'replacer',
      onFile: (page: PluginFile) => ({ ...page, html: 'replaced' }),
    };
    const manager = new PluginManager([plugin]);
    const result = await manager.runOnFile(
      { title: '', date: '', tags: [], slug: 'x', source: 'x.md', html: 'original', raw: '', contentDir: '' },
      makeContext(),
    );
    expect(result.html).toBe('replaced');
  });

  it('skips plugins that do not implement a hook', async () => {
    const plugin: Plugin = { name: 'noop' };
    const manager = new PluginManager([plugin]);
    await expect(manager.runHook('onStart', makeContext())).resolves.toBeUndefined();
  });
});

describe('MarkdownPlugin', () => {
  it('parses frontmatter and renders the body to html', async () => {
    const plugin = new MarkdownPlugin();
    const page: PluginFile = {
      title: '',
      date: '',
      tags: [],
      slug: 'post',
      source: 'post.md',
      html: '',
      raw: '---\ntitle: My Post\ndate: 2024-02-03\ntags: [a, b]\n---\n# Heading',
      contentDir: 'content',
    };
    await plugin.onFile(page, makeContext());
    expect(page.title).toBe('My Post');
    expect(page.date).toBe('2024-02-03');
    expect(page.tags).toEqual(['a', 'b']);
    expect(page.html).toContain('<h1>Heading</h1>');
  });
});

describe('TemplatePlugin', () => {
  it('renders a page through handlebars templates when present', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'templates/default.hbs': '<main>{{{body}}}</main>',
    });
    const plugin = new TemplatePlugin(path.join(dir, 'templates'));
    await plugin.onStart(makeContext());
    const page: PluginFile = {
      title: 'T',
      date: '',
      tags: [],
      slug: 't',
      source: 't.md',
      html: '<p>Body</p>',
      raw: '',
      contentDir: 'content',
    };
    await plugin.onFile(page, makeContext());
    expect(page.html).toContain('<main><p>Body</p></main>');
  });
});

describe('SSGEngine', () => {
  it('orchestrates the plugin pipeline across lifecycle hooks', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\n# One\n',
    });

    const calls: string[] = [];
    const plugin: Plugin = {
      name: 'tracer',
      onStart: () => {
        calls.push('start');
      },
      beforeBuild: () => {
        calls.push('before');
      },
      onFile: (page: PluginFile) => {
        calls.push(`file:${page.slug}`);
      },
      afterBuild: (context: PluginContext) => {
        calls.push(`after:${context.files.length}`);
      },
      onEnd: () => {
        calls.push('end');
      },
    };

    const engine = new SSGEngine({
      plugins: [plugin],
      configPath: path.join(dir, 'no-config.ts'),
    });
    const result = await engine.build(path.join(dir, 'content'), path.join(dir, 'dist'));

    expect(calls).toEqual(['start', 'before', 'file:one', 'after:2', 'end']);
    expect(result.files).toHaveLength(2);
  });

  it('lets custom plugins transform rendered output', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\nBody',
    });

    const plugin: Plugin = {
      name: 'uppercase',
      onFile: (page: PluginFile) => {
        page.html = page.html.toUpperCase();
      },
    };

    const engine = new SSGEngine({
      plugins: [plugin],
      configPath: path.join(dir, 'no-config.ts'),
    });
    await engine.build(path.join(dir, 'content'), path.join(dir, 'dist'));

    const html = readFileSync(path.join(dir, 'dist', 'one.html'), 'utf8');
    expect(html).toContain('<H1>ONE</H1>');
  });

  it('buildSite loads plugins from ssg.config.ts', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/one.md': '---\ntitle: One\n---\nBody',
      'plugins/suffix.ts': `export default class SuffixPlugin {
  name = 'suffix';
  onFile(page) {
    page.html += '<!--suffix-->';
  }
}
`,
      'ssg.config.ts': `import SuffixPlugin from './plugins/suffix';
export default { plugins: [new SuffixPlugin()] };
`,
    });

    const config = loadConfig(path.join(dir, 'ssg.config.ts'));
    expect(config).toBeDefined();
    expect(config?.plugins?.[0]?.name).toBe('suffix');

    await buildSite(path.join(dir, 'content'), path.join(dir, 'dist'), {
      configPath: path.join(dir, 'ssg.config.ts'),
    });
    const html = readFileSync(path.join(dir, 'dist', 'one.html'), 'utf8');
    expect(html).toContain('<!--suffix-->');
  });

  it('returns undefined when the config file does not exist', () => {
    expect(loadConfig(path.join(makeTempDir(), 'missing.ts'))).toBeUndefined();
  });
});

describe('DevServerPlugin', () => {
  it('exposes a dev-server plugin that wraps the serve lifecycle', async () => {
    const dir = makeTempDir();
    writeFixture(dir, {
      'content/hello.md': '---\ntitle: Hello\n---\n# Hello\n',
    });

    const plugin = new DevServerPlugin({
      contentDir: path.join(dir, 'content'),
      outputDir: path.join(dir, 'dist'),
      templatesDir: path.join(dir, 'templates'),
      port: 0,
    });

    expect(plugin.name).toBe('dev-server');
    await plugin.onStart(makeContext());
    expect(plugin.getServer()).not.toBeNull();
    const handle = plugin.toHandle();
    await handle.stop();
    await plugin.onEnd(makeContext());
  });
});
