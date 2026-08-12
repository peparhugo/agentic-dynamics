import { existsSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Page } from '../src/page';
import { Plugin, isPlugin } from '../src/plugin';
import { createEngine } from '../src/ssg';
import { MarkdownPlugin } from '../src/plugins/markdown';
import { TemplatePlugin } from '../src/plugins/template';
import { DevServerPlugin } from '../src/plugins/dev-server';
import { loadPlugins } from '../src/config';
import { buildSite } from '../src/build';
import { createFixture, cleanupFixture, Fixture } from './helpers';

describe('Plugin interface', () => {
  it('recognizes objects with lifecycle hooks as plugins', () => {
    expect(isPlugin({ name: 'a', onStart() {} })).toBe(true);
    expect(isPlugin({ name: 'a', onFile() {} })).toBe(true);
    expect(isPlugin({ name: 'a', onEnd() {} })).toBe(true);
  });

  it('rejects objects without a name or hooks', () => {
    expect(isPlugin({})).toBe(false);
    expect(isPlugin({ name: 'a' })).toBe(false);
    expect(isPlugin('markdown')).toBe(false);
  });
});

describe('built-in plugins', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('MarkdownPlugin parses a page from its filePath', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\ndate: 2024-01-01\ntags: [a, b]\n---\n\nHello **world**.' });
    const page: Page = { slug: 'post', title: '', date: '', tags: [], contentHtml: '', filePath: join(fixture.contentDir, 'post.md') };

    const result = new MarkdownPlugin().onFile(page) as Page;
    expect(result.title).toBe('Post');
    expect(result.date).toBe('2024-01-01T00:00:00.000Z');
    expect(result.tags).toEqual(['a', 'b']);
    expect(result.contentHtml).toContain('<strong>world</strong>');
  });

  it('MarkdownPlugin leaves a page without a filePath untouched', () => {
    const page: Page = { slug: 'x', title: 'X', date: '', tags: [], contentHtml: 'body' };
    const result = new MarkdownPlugin().onFile(page);
    expect(result).toBeUndefined();
  });

  it('TemplatePlugin renders a page and writes page and index output', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });
    const plugin = new TemplatePlugin();
    const context = { contentDir: fixture.contentDir, outputDir: fixture.outputDir, templatesDir: fixture.templatesDir };
    plugin.onStart(context);

    const page: Page = { slug: 'post', title: 'Post', date: '', tags: [], contentHtml: '<p>Body.</p>' };
    const rendered = plugin.onFile(page, context) as Page;
    expect(rendered.html).toContain('<title>Post</title>');
    expect(rendered.html).toContain('<p>Body.</p>');

    plugin.afterBuild(context, [rendered]);
    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
  });

  it('DevServerPlugin creates a watcher and websocket server after onStart', async () => {
    fixture = createFixture({ 'a.md': '# A' });
    const plugin = new DevServerPlugin();
    const context = { contentDir: fixture.contentDir, outputDir: fixture.outputDir, templatesDir: fixture.templatesDir };

    plugin.onStart(context);
    await plugin.ready();

    expect(plugin.watcher).not.toBeNull();
    expect(plugin.wss).toBeDefined();
    await plugin.close();
  });
});

describe('plugin pipeline', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('runs a plugins lifecycle hooks in order across a build', () => {
    fixture = createFixture({ 'a.md': '# A' });
    const order: string[] = [];
    const custom: Plugin = {
      name: 'custom',
      onStart: () => order.push('onStart'),
      beforeBuild: () => order.push('beforeBuild'),
      onFile: (page) => {
        order.push('onFile');
        return page;
      },
      afterBuild: () => order.push('afterBuild'),
      onEnd: () => order.push('onEnd'),
    };

    const engine = createEngine({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templatesDir: fixture.templatesDir,
      plugins: [custom],
    });

    expect(engine.pipeline.map((plugin) => plugin.name)).toEqual(['markdown', 'template', 'custom']);

    engine.start();
    engine.build();

    expect(order).toEqual(['onStart', 'beforeBuild', 'onFile', 'afterBuild', 'onEnd']);
  });

  it('runs built-in onFile hooks before configured plugins', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });
    let observed: Page | undefined;
    const engine = createEngine({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templatesDir: fixture.templatesDir,
      plugins: [
        {
          name: 'observe',
          onFile: (page) => {
            observed = { ...page };
            return page;
          },
        },
      ],
    });
    engine.start();
    engine.build();

    expect(observed?.title).toBe('Post');
    expect(observed?.contentHtml).toContain('Body.');
    expect(observed?.html).toContain('<title>Post</title>');
  });

  it('lets an onFile plugin transform pages before rendering', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });
    const engine = createEngine({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templatesDir: fixture.templatesDir,
      plugins: [
        {
          name: 'rename',
          onFile: (page) => {
            page.title = 'Renamed';
            return page;
          },
        },
      ],
    });
    engine.start();
    const pages = engine.build();

    expect(pages[0].title).toBe('Renamed');
    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<title>Renamed</title>');
  });
});

describe('config loading', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('loads plugins declared in an ssg.config.ts file', () => {
    fixture = createFixture({});
    const configPath = join(fixture.root, 'ssg.config.ts');
    writeFileSync(
      configPath,
      [
        'export default {',
        '  plugins: [',
        '    {',
        '      name: "custom",',
        '      onStart: () => {},',
        '      onFile: (page: any) => { page.title = "Mutated"; return page; },',
        '    },',
        '  ],',
        '};',
      ].join('\n')
    );

    const plugins = loadPlugins(configPath);
    expect(plugins).toHaveLength(1);
    expect(plugins[0].name).toBe('custom');
  });

  it('resolves built-in plugins by name from the config', () => {
    fixture = createFixture({});
    const configPath = join(fixture.root, 'ssg.config.ts');
    writeFileSync(configPath, 'export default { plugins: ["markdown", "template"] };\n');

    const plugins = loadPlugins(configPath);
    expect(plugins.map((plugin) => plugin.name)).toEqual(['markdown', 'template']);
  });

  it('returns an empty list when no config exists', () => {
    expect(loadPlugins(join(require('os').tmpdir(), 'does-not-exist-ssg', 'ssg.config.ts'))).toEqual([]);
  });

  it('runs a config plugin through a full engine build', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });
    const configPath = join(fixture.root, 'ssg.config.ts');
    writeFileSync(
      configPath,
      [
        'export default {',
        '  plugins: [',
        '    {',
        '      name: "custom",',
        '      onFile: (page: any) => { page.title = "Customized"; return page; },',
        '    },',
        '  ],',
        '};',
      ].join('\n')
    );

    const engine = createEngine({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templatesDir: fixture.templatesDir,
      plugins: loadPlugins(configPath),
    });
    engine.start();
    const pages = engine.build();

    expect(pages[0].title).toBe('Customized');
  });

  it('keeps the default built-in pipeline when no config is present', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });
    const engine = createEngine({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templatesDir: fixture.templatesDir,
    });

    expect(engine.pipeline.map((plugin) => plugin.name)).toEqual(['markdown', 'template']);

    engine.start();
    const pages = engine.build();
    expect(pages[0].title).toBe('Post');
    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
  });

  it('buildSite keeps external behavior identical', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\ntags: [x]\n---\n\nHello **world**.' });
    const pages = buildSite(fixture.contentDir, fixture.outputDir);
    expect(pages).toHaveLength(1);
    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
  });
});
