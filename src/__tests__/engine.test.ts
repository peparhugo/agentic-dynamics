import fs from 'fs';
import os from 'os';
import path from 'path';

import { createEngine, SSGEngine } from '../engine';
import { loadPages } from '../load';
import { buildSite } from '../site';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

describe('SSGEngine', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-engine-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    writeTree(contentDir, { 'a.md': '---\ntitle: Alpha\n---\n# Body A' });
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('runs the plugin lifecycle in order around a build', () => {
    const events: string[] = [];
    const recorder: Plugin = {
      name: 'recorder',
      onStart: () => events.push('onStart'),
      beforeBuild: () => events.push('beforeBuild'),
      onFile: (page) => events.push(`onFile:${page.slug}`),
      afterBuild: () => events.push('afterBuild'),
      onEnd: () => events.push('onEnd'),
    };

    const engine = createEngine({
      contentDir,
      outputDir,
      templatesDir: path.join(outputDir, 'missing'),
      plugins: [recorder],
    });

    const pages = engine.run();

    expect(pages).toHaveLength(1);
    expect(events).toEqual(['onStart', 'beforeBuild', 'onFile:a', 'afterBuild', 'onEnd']);
  });

  it('provides loaded pages and outputs to the plugin context', () => {
    const seen: { pages: number; outputs: string[] } = { pages: 0, outputs: [] };
    const spy: Plugin = {
      name: 'spy',
      onEnd: (context) => {
        seen.pages = context.pages.length;
        seen.outputs = Object.keys(context.outputs);
      },
    };

    createEngine({
      contentDir,
      outputDir,
      templatesDir: path.join(outputDir, 'missing'),
      plugins: [spy],
    }).run();

    expect(seen.pages).toBe(1);
    expect(seen.outputs).toContain('a.html');
    expect(seen.outputs).toContain('index.html');
  });

  it('writes pages through a plugin-provided output override', () => {
    const uppercaser: Plugin = {
      name: 'uppercaser',
      onFile: (page, context) => {
        context.outputs[page.outputName] = `UPPER ${page.title}`;
      },
    };

    createEngine({
      contentDir,
      outputDir,
      templatesDir: path.join(outputDir, 'missing'),
      plugins: [uppercaser],
    }).run();

    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toBe('UPPER Alpha');
  });

  it('exposes the pipeline and context', () => {
    const plugin: Plugin = { name: 'p' };
    const engine = new SSGEngine([plugin], { options: { contentDir, outputDir }, pages: [], outputs: {} }, { contentDir, outputDir });
    expect(engine.pipeline.plugins).toHaveLength(1);
    expect(engine.context.outputs).toEqual({});
  });
});

describe('engine plugin integration', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-engine-int-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('MarkdownPlugin converts an unrendered page body', () => {
    const plugin = new MarkdownPlugin();
    const page = { ...readPageFixture(), content: '# Hi', html: '' };
    const context: PluginContext = { options: { contentDir, outputDir }, pages: [page], outputs: {} };

    plugin.onFile(page, context);

    expect(page.html).toContain('<h1>Hi</h1>');
  });

  it('MarkdownPlugin leaves already-rendered pages untouched', () => {
    const plugin = new MarkdownPlugin();
    const page = readPageFixture();
    page.html = '<h1>Rendered</h1>';
    const context: PluginContext = { options: { contentDir, outputDir }, pages: [page], outputs: {} };

    plugin.onFile(page, context);

    expect(page.html).toBe('<h1>Rendered</h1>');
  });

  it('TemplatePlugin renders pages and the index into the outputs map', () => {
    writeTree(contentDir, { 'b.md': '---\ntitle: Beta\n---\n# Body B' });
    const templatesDir = path.join(root, 'templates');
    writeTree(templatesDir, {
      'default.hbs': '<article>{{title}}</article>',
      'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
      'index.hbs': '{{#each pages}}<li>{{title}}</li>{{/each}}',
    });

    const context: PluginContext = {
      options: { contentDir, outputDir, templatesDir },
      pages: loadPages(contentDir),
      outputs: {},
    };

    const plugin = new TemplatePlugin();
    plugin.beforeBuild(context);
    for (const page of context.pages) {
      plugin.onFile(page, context);
    }
    plugin.afterBuild(context);

    expect(context.outputs['b.html']).toContain('<article>Beta</article>');
    expect(context.outputs['b.html']).toContain('<html><body>');
    expect(context.outputs['index.html']).toContain('<li>Beta</li>');
  });

  it('TemplatePlugin falls back to the built-in renderers without templates', () => {
    writeTree(contentDir, { 'c.md': '---\ntitle: Gamma\n---\nBody C' });

    const pages = buildSite({
      contentDir,
      outputDir,
      templatesDir: path.join(outputDir, 'missing'),
    });

    expect(fs.readFileSync(path.join(outputDir, 'c.html'), 'utf8')).toContain('<h1>Gamma</h1>');
    expect(pages).toHaveLength(1);
  });
});

function readPageFixture(): Page {
  return {
    slug: 'x',
    sourcePath: 'x.md',
    outputName: 'x.html',
    title: 'X',
    tags: [],
    html: '<p>body</p>',
    content: 'body',
    raw: 'body',
    data: { title: 'X' },
  };
}
