import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { SsgEngine } from '../src/engine';
import type { Plugin, PluginContext } from '../src/plugin';
import type { Page } from '../src/types';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

/** Records every hook invocation (with the plugin's own label) in a shared array, for asserting pipeline order. */
function recordingPlugin(label: string, calls: string[], onFileFn?: (page: Page) => Page | void): Plugin {
  return {
    name: label,
    onStart(_ctx: PluginContext) {
      calls.push(`${label}:onStart`);
    },
    beforeBuild(_ctx: PluginContext) {
      calls.push(`${label}:beforeBuild`);
    },
    onFile(page: Page, _ctx: PluginContext) {
      calls.push(`${label}:onFile:${page.sourcePath}`);
      return onFileFn?.(page);
    },
    afterBuild(pages: Page[], _ctx: PluginContext) {
      calls.push(`${label}:afterBuild:${pages.length}`);
    },
    onEnd(_ctx: PluginContext) {
      calls.push(`${label}:onEnd`);
    },
  };
}

describe('SsgEngine', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-engine-content-');
    outputDir = makeTempDir('ssg-engine-output-');
    templatesDir = makeTempDir('ssg-engine-templates-');

    writeFile(path.join(contentDir, 'a.md'), 'A body');
    writeFile(path.join(contentDir, 'b.md'), 'B body');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('throws when the content directory does not exist', () => {
    const engine = new SsgEngine({
      contentDir: path.join(contentDir, 'nope'),
      outputDir,
      templatesDir,
      plugins: [],
    });
    expect(() => engine.build()).toThrow(/Content directory not found/);
  });

  it('runs every plugin through each hook, in plugin order, before moving to the next hook', () => {
    const calls: string[] = [];
    const engine = new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [recordingPlugin('first', calls), recordingPlugin('second', calls)],
    });

    engine.build();

    // Every plugin's onStart runs before any plugin's beforeBuild, and so on down the pipeline.
    expect(calls).toEqual([
      'first:onStart',
      'second:onStart',
      'first:beforeBuild',
      'second:beforeBuild',
      'first:onFile:a.md',
      'second:onFile:a.md',
      'first:onFile:b.md',
      'second:onFile:b.md',
      'first:afterBuild:2',
      'second:afterBuild:2',
      'first:onEnd',
      'second:onEnd',
    ]);
  });

  it('threads a page transformed by one plugin through to the next plugin', () => {
    const calls: string[] = [];
    const engine = new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [
        recordingPlugin('tagger', calls, (page) => ({ ...page, tags: ['tagged'] })),
        recordingPlugin('checker', calls, (page) => {
          expect(page.tags).toEqual(['tagged']);
        }),
      ],
    });

    const result = engine.build();
    expect(result.pages.every((p) => p.tags.includes('tagged'))).toBe(true);
  });

  it('returns pages built from bare page skeletons when no plugin sets metadata', () => {
    const engine = new SsgEngine({ contentDir, outputDir, templatesDir, plugins: [] });
    const result = engine.build();

    expect(result.pages).toHaveLength(2);
    expect(result.pages.map((p) => p.sourcePath).sort()).toEqual(['a.md', 'b.md']);
    expect(result.pages.every((p) => p.html === '')).toBe(true);
  });

  it('exposes the config passed on EngineOptions to every hook via ctx.config', () => {
    let seenConfig: unknown;
    const plugin: Plugin = {
      name: 'config-reader',
      beforeBuild(ctx) {
        seenConfig = ctx.config;
      },
    };

    const engine = new SsgEngine({
      contentDir,
      outputDir,
      templatesDir,
      plugins: [plugin],
      config: { siteName: 'My Site' },
    });

    engine.build();
    expect(seenConfig).toEqual({ siteName: 'My Site' });
  });
});
