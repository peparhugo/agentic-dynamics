import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from './build';
import { Plugin } from './types';

describe('plugin pipeline', () => {
  let root: string;

  beforeEach(async () => { root = await mkdtemp(join(tmpdir(), 'ssg-plugins-')); });
  afterEach(async () => { await rm(root, { recursive: true, force: true }); });

  it('runs every lifecycle hook in declaration order', async () => {
    const content = join(root, 'content');
    const events: string[] = [];
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'post.md'), 'source');
    const first: Plugin = {
      onStart: () => { events.push('first:start'); },
      beforeBuild: () => { events.push('first:before'); },
      onFile: (page) => {
        events.push('first:file');
        page.metadata = { title: 'Post', tags: [] };
        page.html = '<p>Post</p>';
      },
      afterBuild: () => { events.push('first:after'); },
      onEnd: () => { events.push('first:end'); },
    };
    const second: Plugin = {
      onStart: () => { events.push('second:start'); },
      beforeBuild: () => { events.push('second:before'); },
      onFile: (page) => {
        events.push('second:file');
        page.renderedHtml = '<html>Post</html>';
      },
      afterBuild: () => { events.push('second:after'); },
      onEnd: () => { events.push('second:end'); },
    };

    await buildSite(content, join(root, 'dist'), join(root, 'templates'), [first, second]);

    expect(events).toEqual([
      'first:start', 'second:start', 'first:before', 'second:before',
      'first:file', 'second:file', 'first:after', 'second:after',
      'first:end', 'second:end',
    ]);
  });
});
