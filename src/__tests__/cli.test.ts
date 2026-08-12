import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { parseArgs, run } from '../cli';

describe('parseArgs', () => {
  it('defaults content and output directories', () => {
    const result = parseArgs(['node', 'ssg', 'build']);
    expect(result.command).toBe('build');
    expect(result.options.contentDir).toBe('./content');
    expect(result.options.outputDir).toBe('./dist');
  });

  it('reads --content and --output options', () => {
    const result = parseArgs([
      'node',
      'ssg',
      'build',
      '--content',
      './pages',
      '--output',
      './site',
    ]);
    expect(result.options.contentDir).toBe('./pages');
    expect(result.options.outputDir).toBe('./site');
  });

  it('supports short flags', () => {
    const result = parseArgs(['node', 'ssg', 'build', '-c', './pages', '-o', './site']);
    expect(result.options.contentDir).toBe('./pages');
    expect(result.options.outputDir).toBe('./site');
  });

  it('throws on an unknown option', () => {
    expect(() => parseArgs(['node', 'ssg', 'build', '--bogus'])).toThrow(
      'Unknown option or command'
    );
  });
});

describe('run', () => {
  it('builds the site end to end', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'out');

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, 'about.md'),
      '---\ntitle: About Us\ntags: [meta]\n---\n# About\nWe make static sites.'
    );

    await run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir]);

    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('About Us');

    const about = await fs.readFile(path.join(outputDir, 'about.html'), 'utf-8');
    expect(about).toContain('We make static sites.');
  });
});
