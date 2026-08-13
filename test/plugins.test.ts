import fs from 'fs';
import os from 'os';
import path from 'path';
import { PluginPipeline } from '../src/plugin';
import type { Plugin, PluginContext } from '../src/plugin';
import { SSGEngine } from '../src/core';
import { MarkdownPlugin } from '../src/plugins/MarkdownPlugin';
import { TemplatePlugin } from '../src/plugins/TemplatePlugin';
import { loadPluginsFromConfig, resolvePluginEntry } from '../src/config';
import { buildSite } from '../src/build';
import type { Page } from '../src/types';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-'));
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

function writeFiles(root: string, files: Record<string, string>): void {
  fs.mkdirSync(root, { recursive: true });
  for (const [name, contents] of Object.entries(files)) {
    const file = path.join(root, name);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, contents, 'utf-8');
  }
}

function read(dir: string, file: string): string {
  return fs.readFileSync(path.join(dir, file), 'utf-8');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'post',
    sourcePath: 'post.md',
    data: {},
    body: '',
    html: '',
    outputFile: 'post.html',
    ...overrides,
  };
}

describe('PluginPipeline', () => {
  it('runs every hook across plugins in registration order', () => {
    const calls: string[] = [];
    const a: Plugin = {
      name: 'a',
      onStart: () => calls.push('a.onStart'),
      beforeBuild: () => calls.push('a.beforeBuild'),
      afterBuild: () => calls.push('a.afterBuild'),
      onFile: () => calls.push('a.onFile'),
      onEnd: () => calls.push('a.onEnd'),
    };
    const b: Plugin = {
      name: 'b',
      onStart: () => calls.push('b.onStart'),
      beforeBuild: () => calls.push('b.beforeBuild'),
      afterBuild: () => calls.push('b.afterBuild'),
      onFile: () => calls.push('b.onFile'),
      onEnd: () => calls.push('b.onEnd'),
    };

    const pipeline = new PluginPipeline([a, b]);
    const page = makePage();
    const ctx = {} as PluginContext;

    pipeline.runHook('onStart', ctx);
    pipeline.runHook('beforeBuild', ctx);
    pipeline.runHook('onFile', page, ctx);
    pipeline.runHook('afterBuild', ctx);
    pipeline.runHook('onEnd', ctx);

    expect(calls).toEqual([
      'a.onStart',
      'b.onStart',
      'a.beforeBuild',
      'b.beforeBuild',
      'a.onFile',
      'b.onFile',
      'a.afterBuild',
      'b.afterBuild',
      'a.onEnd',
      'b.onEnd',
    ]);
  });

  it('skips hooks a plugin does not implement', () => {
    const pipeline = new PluginPipeline([{ name: 'minimal' }]);
    expect(() => pipeline.runHook('beforeBuild', {})).not.toThrow();
  });

  it('supports registering plugins after construction', () => {
    const calls: string[] = [];
    const pipeline = new PluginPipeline();
    pipeline.register({ name: 'late', onStart: () => calls.push('late') });
    pipeline.runHook('onStart', {} as PluginContext);
    expect(calls).toEqual(['late']);
  });
});

describe('built-in plugins', () => {
  it('MarkdownPlugin parses frontmatter and renders markdown', () => {
    const root = makeTempDir();
    try {
      writeFiles(root, { 'post.md': '---\ntitle: Hi\n---\n# Hello\n' });
      const plugin = new MarkdownPlugin();
      const page = makePage();
      plugin.onFile(page, { contentDir: root, outputDir: root, pages: [] } as PluginContext);

      expect(page.data.title).toBe('Hi');
      expect(page.html).toContain('<h1>Hello</h1>');
    } finally {
      cleanup(root);
    }
  });

  it('TemplatePlugin renders a page template with the site context', () => {
    const root = makeTempDir();
    try {
      writeFiles(root, { 'templates/default.hbs': '<title>{{title}}</title>{{{body}}}' });
      const plugin = new TemplatePlugin();
      const ctx = {
        contentDir: root,
        outputDir: root,
        templatesDir: path.join(root, 'templates'),
        pages: [],
        site: { pages: [{ slug: 'post', title: 'Hi', outputFile: 'post.html' }] },
      } as PluginContext;

      plugin.beforeBuild(ctx);
      const page = makePage({ data: { title: 'Hi' }, body: '# Hello', html: '<h1>Hello</h1>' });
      plugin.onFile(page, ctx);

      expect(page.templated).toBe('<title>Hi</title><h1>Hello</h1>');
    } finally {
      cleanup(root);
    }
  });
});

describe('SSGEngine plugin pipeline', () => {
  it('runs lifecycle hooks in order around a build', () => {
    const root = makeTempDir();
    try {
      const contentDir = path.join(root, 'content');
      writeFiles(contentDir, { 'a.md': '# A', 'b.md': '# B' });

      const calls: string[] = [];
      class Recorder implements Plugin {
        readonly name = 'recorder';
        onStart(): void {
          calls.push('onStart');
        }
        beforeBuild(): void {
          calls.push('beforeBuild');
        }
        afterBuild(): void {
          calls.push('afterBuild');
        }
        onFile(): void {
          calls.push('onFile');
        }
        onEnd(): void {
          calls.push('onEnd');
        }
      }

      const engine = new SSGEngine({
        contentDir,
        outputDir: path.join(root, 'dist'),
        plugins: [new Recorder(), new MarkdownPlugin(), new TemplatePlugin()],
      });
      engine.start();
      const result = engine.build();
      engine.stop();

      expect(result.pages).toHaveLength(2);
      expect(calls[0]).toBe('onStart');
      expect(calls[calls.length - 1]).toBe('onEnd');
      const firstOnFile = calls.indexOf('onFile');
      const afterBuild = calls.indexOf('afterBuild');
      expect(firstOnFile).toBeGreaterThan(calls.indexOf('beforeBuild'));
      expect(firstOnFile).toBeLessThan(afterBuild);
      expect(calls.filter((c) => c === 'onFile')).toHaveLength(4);
    } finally {
      cleanup(root);
    }
  });

  it('builds pages through the markdown and template plugins', () => {
    const root = makeTempDir();
    try {
      const contentDir = path.join(root, 'content');
      const templatesDir = path.join(root, 'templates');
      const outputDir = path.join(root, 'dist');
      writeFiles(contentDir, { 'post.md': '---\ntitle: Post\n---\n# Body' });
      writeFiles(templatesDir, { 'default.hbs': '<html><body>{{title}}:{{{body}}}</body></html>' });

      const engine = new SSGEngine({
        contentDir,
        outputDir,
        templatesDir,
        plugins: [new MarkdownPlugin(), new TemplatePlugin()],
      });
      const result = engine.build();

      const html = read(outputDir, 'post.html');
      expect(html).toContain('Post:<h1>Body</h1>');
      expect(result.indexFile).toBe(path.join(outputDir, 'index.html'));
    } finally {
      cleanup(root);
    }
  });

  it('buildSite still works through the plugin pipeline', () => {
    const root = makeTempDir();
    try {
      const contentDir = path.join(root, 'content');
      const templatesDir = path.join(root, 'templates');
      const outputDir = path.join(root, 'dist');
      writeFiles(contentDir, { 'post.md': '---\ntitle: Plug\n---\n# Plug' });
      writeFiles(templatesDir, { 'default.hbs': '<main class="plugin">{{{body}}}</main>' });

      buildSite(contentDir, outputDir, templatesDir);

      const html = read(outputDir, 'post.html');
      expect(html).toContain('class="plugin"');
      expect(html).toContain('<h1>Plug</h1>');
    } finally {
      cleanup(root);
    }
  });

  it('runs a custom plugin hook during a build', () => {
    const root = makeTempDir();
    try {
      const contentDir = path.join(root, 'content');
      const outputDir = path.join(root, 'dist');
      writeFiles(contentDir, { 'post.md': '# Post' });

      const notes: string[] = [];
      class Custom implements Plugin {
        readonly name = 'custom';
        onStart(): void {
          notes.push('start');
        }
        beforeBuild(): void {
          notes.push('before');
        }
        afterBuild(): void {
          notes.push('after');
        }
        onEnd(): void {
          notes.push('end');
        }
      }

      const engine = new SSGEngine({
        contentDir,
        outputDir,
        plugins: [new Custom(), new MarkdownPlugin()],
      });
      engine.start();
      engine.build();
      engine.stop();

      expect(notes).toEqual(['start', 'before', 'after', 'end']);
    } finally {
      cleanup(root);
    }
  });
});

describe('config loading', () => {
  it('loads the project ssg.config.ts by default', () => {
    const plugins = loadPluginsFromConfig();
    expect(plugins.map((p) => p.name).sort()).toEqual(['markdown', 'template']);
  });

  it('falls back to built-in plugins when the config is missing', () => {
    const root = makeTempDir();
    try {
      const plugins = loadPluginsFromConfig(path.join(root, 'missing.ts'));
      expect(plugins.map((p) => p.name).sort()).toEqual(['markdown', 'template']);
    } finally {
      cleanup(root);
    }
  });

  it('loads plugins declared in a config file', () => {
    const root = makeTempDir();
    try {
      const cfgPath = path.join(root, 'ssg.config.ts');
      writeFiles(path.dirname(cfgPath), {
        'ssg.config.ts': [
          `import { MarkdownPlugin } from '${path.resolve(__dirname, '..')}/src/plugins';`,
          'export default { plugins: [MarkdownPlugin] };',
        ].join('\n'),
      });

      const plugins = loadPluginsFromConfig(cfgPath);
      expect(plugins.map((p) => p.name)).toEqual(['markdown']);
    } finally {
      cleanup(root);
    }
  });

  it('accepts plugin instances and classes as config entries', () => {
    const entries = [new MarkdownPlugin(), TemplatePlugin];
    const resolved = entries.map(resolvePluginEntry);
    expect(resolved.map((p) => p.name)).toEqual(['markdown', 'template']);
  });
});
