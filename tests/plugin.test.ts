import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator';

describe('plugin pipeline', () => {
  let root: string;

  beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'ssg-plugin-')); });
  afterEach(() => { rmSync(root, { recursive: true, force: true }); });

  it('loads configured plugins and invokes lifecycle hooks in order', () => {
    const content = join(root, 'content');
    const config = join(root, 'ssg.config.ts');
    mkdirSync(content);
    writeFileSync(join(content, 'page.md'), '# Page');
    writeFileSync(config, `
      const events = globalThis.__ssgPluginEvents;
      export default { plugins: [{
        onStart() { events.push('start'); },
        beforeBuild() { events.push('before'); },
        onFile() { events.push('file'); },
        afterBuild() { events.push('after'); },
        onEnd() { events.push('end'); },
      }] };
    `);
    (globalThis as typeof globalThis & { __ssgPluginEvents: string[] }).__ssgPluginEvents = [];

    buildSite({ contentDir: content, outputDir: join(root, 'output'), configPath: config });

    expect((globalThis as typeof globalThis & { __ssgPluginEvents: string[] }).__ssgPluginEvents).toEqual(['start', 'before', 'file', 'after', 'end']);
  });
});
