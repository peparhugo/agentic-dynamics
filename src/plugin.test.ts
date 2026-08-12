import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from './build';
import { SSG } from './engine';
import { loadConfig } from './config';
import { builtinPlugins } from './plugins';
import { Plugin } from './plugin';

describe('Plugin pipeline', () => {
  it('runs onStart hooks in plugin order', () => {
    const order: string[] = [];
    const mk = (name: string): Plugin => ({
      name,
      onStart() {
        order.push(`${name}.onStart`);
      },
      beforeBuild() {
        order.push(`${name}.beforeBuild`);
      },
      afterBuild() {
        order.push(`${name}.afterBuild`);
      },
      onEnd() {
        order.push(`${name}.onEnd`);
      },
    });

    const engine = new SSG({
      options: { contentDir: '/none', outputDir: '/none' },
      plugins: [mk('a'), mk('b')],
    });
    engine.start();
    expect(order).toEqual(['a.onStart', 'b.onStart']);
  });

  it('runs the full pipeline in order across plugins', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-pipe-'));
    try {
      const order: string[] = [];
      const mk = (name: string): Plugin => ({
        name,
        beforeBuild() {
          order.push(`${name}.beforeBuild`);
        },
        afterBuild() {
          order.push(`${name}.afterBuild`);
        },
        onEnd() {
          order.push(`${name}.onEnd`);
        },
      });

      const engine = new SSG({
        options: { contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') },
        plugins: [mk('a'), mk('b')],
      });
      fs.mkdirSync(path.join(root, 'content'));
      engine.build();
      expect(order).toEqual([
        'a.beforeBuild',
        'b.beforeBuild',
        'a.afterBuild',
        'b.afterBuild',
        'a.onEnd',
        'b.onEnd',
      ]);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it('lets a plugin transform pages through onFile', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-'));
    try {
      const contentDir = path.join(root, 'content');
      const outputDir = path.join(root, 'dist');
      fs.mkdirSync(contentDir);
      fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\n\nbody', 'utf-8');

      const stamp: Plugin = {
        name: 'stamp',
        onFile(page) {
          return { ...page, data: { ...page.data, title: `${page.data.title ?? ''}!` } };
        },
      };

      const engine = new SSG({
        options: { contentDir, outputDir },
        plugins: [...builtinPlugins(), stamp],
      });
      engine.start();
      const pages = engine.build();

      expect(pages).toHaveLength(1);
      expect(pages[0].data.title).toBe('A!');
      expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it('runs a custom plugin through buildSite-equivalent engine', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin2-'));
    try {
      const contentDir = path.join(root, 'content');
      const outputDir = path.join(root, 'dist');
      fs.mkdirSync(contentDir);
      fs.writeFileSync(path.join(contentDir, 'b.md'), '---\ntitle: B\n---\n\nx', 'utf-8');

      const config = loadConfig();
      const extra: Plugin = {
        name: 'extra',
        afterBuild(ctx) {
          ctx.writeFile('extra.txt', `pages:${ctx.pages.length}`);
        },
      };

      const engine = new SSG({
        options: { contentDir, outputDir },
        plugins: [...config.plugins, extra],
      });
      engine.start();
      engine.build();

      expect(fs.readFileSync(path.join(outputDir, 'extra.txt'), 'utf-8')).toBe('pages:1');
      expect(buildSite({ contentDir, outputDir }).length).toBe(1);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});

describe('loadConfig', () => {
  it('loads plugins from ssg.config.ts', () => {
    const cfg = loadConfig();
    expect(cfg.plugins.map((p) => p.name)).toEqual(['markdown', 'template']);
  });

  it('falls back to built-in plugins when the config file is missing', () => {
    const cfg = loadConfig(path.join(os.tmpdir(), 'missing-ssg.config.ts'));
    expect(cfg.plugins.map((p) => p.name)).toEqual(['markdown', 'template']);
  });
});
