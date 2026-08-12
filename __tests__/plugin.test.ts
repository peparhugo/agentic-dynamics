import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';
import { SSGEngine } from '../src/engine';
import { Plugin } from '../src/plugin';
import { Page } from '../src/types';

function makeTempRoot(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const filePath = path.join(root, rel);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
}

describe('plugin system', () => {
  it('runs all lifecycle hooks in order', () => {
    const root = makeTempRoot('ssg-plug-');
    writeTree(root, {
      'content/x.md': '---\ntitle: X\n---\nBody.',
    });
    const outputDir = path.join(root, 'dist');
    const order: string[] = [];

    const trace: Plugin = {
      name: 'trace',
      onStart: () => {
        order.push('onStart');
      },
      beforeBuild: () => {
        order.push('beforeBuild');
      },
      onFile: (page: Page) => {
        order.push(`onFile:${page.slug}`);
        return page;
      },
      afterBuild: () => {
        order.push('afterBuild');
      },
      onEnd: () => {
        order.push('onEnd');
      },
    };

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      plugins: [trace],
    });

    expect(order).toEqual(['onStart', 'beforeBuild', 'onFile:x', 'afterBuild', 'onEnd']);
  });

  it('lets a plugin transform pages before rendering', () => {
    const root = makeTempRoot('ssg-plug-');
    writeTree(root, {
      'content/about.md': '---\ntitle: About\n---\nAbout me.',
    });
    const outputDir = path.join(root, 'dist');

    const shouter: Plugin = {
      name: 'shouter',
      onFile: (page: Page) => ({ ...page, title: page.title.toUpperCase() }),
    };

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      plugins: [shouter],
    });

    const html = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf8');
    expect(html).toContain('<title>ABOUT</title>');
    expect(html).not.toContain('<title>About</title>');
  });

  it('always includes the built-in markdown and template plugins', () => {
    const root = makeTempRoot('ssg-plug-');
    writeTree(root, {
      'content/a.md': '---\ntitle: A\n---\nHello **world**.',
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      plugins: [],
    });

    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<title>A</title>');
    expect(html).toContain('<strong>world</strong>');
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('loads plugins from a config file', () => {
    const root = makeTempRoot('ssg-plug-');
    writeTree(root, {
      'content/x.md': '---\ntitle: X\n---\nBody.',
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      configPath: path.join(__dirname, 'fixtures', 'ssg.config.ts'),
    });

    expect(fs.existsSync(path.join(outputDir, 'plugin-ran.txt'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'x.html'))).toBe(true);
  });

  it('exposes plugins through the engine', () => {
    const engine = new SSGEngine({});
    expect(engine.pluginList.map((plugin) => plugin.name)).toEqual([
      'markdown',
      'template',
    ]);
  });
});
