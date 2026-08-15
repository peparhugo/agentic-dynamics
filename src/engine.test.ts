import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { SSGEngine } from './engine';
import { Page } from './page';
import { Plugin } from './plugin';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('SSGEngine', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-engine-content-');
    outputDir = makeTmpDir('ssg-engine-output-');
    templatesDir = makeTmpDir('ssg-engine-templates-');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('runs hooks in the documented order: onStart, beforeBuild, onFile per file, afterBuild, onEnd', () => {
    fs.writeFileSync(path.join(contentDir, 'a.md'), 'A body');
    fs.writeFileSync(path.join(contentDir, 'b.md'), 'B body');

    const calls: string[] = [];
    const plugin: Plugin = {
      name: 'recorder',
      onStart: () => calls.push('onStart'),
      beforeBuild: () => calls.push('beforeBuild'),
      onFile: (page) => {
        calls.push(`onFile:${page.slug}`);
      },
      afterBuild: (pages) => {
        calls.push(`afterBuild:${pages.length}`);
      },
      onEnd: () => calls.push('onEnd'),
    };

    const engine = new SSGEngine({ contentDir, outputDir, templatesDir, plugins: [plugin] });
    engine.run();

    expect(calls).toEqual(['onStart', 'beforeBuild', 'onFile:a', 'onFile:b', 'afterBuild:2', 'onEnd']);
  });

  it('discovers content files and hands each one a stub Page with slug/outputPath/sourcePath set', () => {
    fs.mkdirSync(path.join(contentDir, 'posts'));
    fs.writeFileSync(path.join(contentDir, 'posts', 'nested.md'), 'Nested body');

    const seen: Page[] = [];
    const plugin: Plugin = {
      name: 'capture',
      onFile: (page) => {
        seen.push(page);
      },
    };

    new SSGEngine({ contentDir, outputDir, templatesDir, plugins: [plugin] }).build();

    expect(seen).toHaveLength(1);
    expect(seen[0].slug).toBe('posts/nested');
    expect(seen[0].outputPath).toBe('posts/nested.html');
    expect(seen[0].sourcePath).toBe(path.join(contentDir, 'posts', 'nested.md'));
  });

  it('lets a plugin replace the page object seen by later plugins', () => {
    fs.writeFileSync(path.join(contentDir, 'only.md'), 'Body');

    const seenTitles: string[] = [];
    const rename: Plugin = {
      name: 'rename',
      onFile: (page) => ({ ...page, title: 'Renamed' }),
    };
    const observe: Plugin = {
      name: 'observe',
      onFile: (page) => {
        seenTitles.push(page.title);
      },
    };

    new SSGEngine({ contentDir, outputDir, templatesDir, plugins: [rename, observe] }).build();

    expect(seenTitles).toEqual(['Renamed']);
  });

  it('throws a clear error when the content directory does not exist', () => {
    const missingDir = path.join(contentDir, 'does-not-exist');
    const engine = new SSGEngine({ contentDir: missingDir, outputDir, templatesDir, plugins: [] });
    expect(() => engine.build()).toThrow(/not found/i);
  });
});
