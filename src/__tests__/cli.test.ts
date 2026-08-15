import fs from 'fs';
import os from 'os';
import path from 'path';

import { main, parseArgs, USAGE } from '../cli';

describe('parseArgs', () => {
  it('uses defaults for content and output', () => {
    const options = parseArgs(['build']);
    expect(options.command).toBe('build');
    expect(options.contentDir).toBe(path.resolve('content'));
    expect(options.outputDir).toBe(path.resolve('dist'));
    expect(options.help).toBe(false);
  });

  it('parses --content and --output', () => {
    const options = parseArgs(['build', '--content', 'src/md', '--output', 'public']);
    expect(options.command).toBe('build');
    expect(options.contentDir).toBe(path.resolve('src/md'));
    expect(options.outputDir).toBe(path.resolve('public'));
  });

  it('parses short flags -c and -o', () => {
    const options = parseArgs(['build', '-c', 'c', '-o', 'o']);
    expect(options.contentDir).toBe(path.resolve('c'));
    expect(options.outputDir).toBe(path.resolve('o'));
  });

  it('detects the help flag', () => {
    expect(parseArgs(['--help']).help).toBe(true);
    expect(parseArgs(['-h']).help).toBe(true);
  });

  it('does not require the command for flags', () => {
    const options = parseArgs(['--content', 'x', '--output', 'y']);
    expect(options.contentDir).toBe(path.resolve('x'));
    expect(options.outputDir).toBe(path.resolve('y'));
  });
});

describe('main', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-content-'));
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-dist-'));
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('returns 0 and builds the site for the build command', () => {
    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      '---\ntitle: Post\n---\n# Post body'
    );

    const code = main(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir]);

    expect(code).toBe(0);
    expect(fs.existsSync(path.join(outputDir, 'post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('returns 1 for an unknown command', () => {
    const code = main(['node', 'ssg', 'serve']);
    expect(code).toBe(1);
  });

  it('returns 0 and prints usage for --help', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => {});
    const code = main(['node', 'ssg', '--help']);
    expect(code).toBe(0);
    expect(spy).toHaveBeenCalledWith(USAGE);
    spy.mockRestore();
  });
});
