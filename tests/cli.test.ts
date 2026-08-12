import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseArgs } from '../src/cli';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-test-'));
}

describe('parseArgs', () => {
  it('uses defaults when invoked as npx ssg build', () => {
    const options = parseArgs(['node', 'ssg', 'build']);
    expect(options.command).toBe('build');
    expect(options.contentDir).toBe('./content');
    expect(options.outputDir).toBe('./dist');
  });

  it('respects --content and --output', () => {
    const options = parseArgs(['node', 'ssg', 'build', '--content', 'docs', '--output', 'public']);
    expect(options.contentDir).toBe('docs');
    expect(options.outputDir).toBe('public');
  });

  it('supports equals syntax', () => {
    const options = parseArgs(['node', 'ssg', 'build', '--content=posts', '--output=site']);
    expect(options.contentDir).toBe('posts');
    expect(options.outputDir).toBe('site');
  });
});

describe('CLI integration', () => {
  it('builds a site with custom content and output directories', () => {
    const root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    fs.mkdirSync(contentDir, { recursive: true });
    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      '---\ntitle: Post\n---\n# Post',
      'utf8',
    );

    const spy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
    const { run } = require('../src/cli');

    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir]);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'post.html'))).toBe(true);
    expect(spy).toHaveBeenCalledWith('Built 1 pages into ' + outputDir);
    spy.mockRestore();
  });
});
