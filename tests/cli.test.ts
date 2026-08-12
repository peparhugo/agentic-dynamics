import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { parseCliArgs, run } from '../src/cli';

describe('parseCliArgs', () => {
  it('uses defaults when no options are given', () => {
    const options = parseCliArgs(['node', 'ssg', 'build']);
    expect(options.contentDir).toBe('./content');
    expect(options.outputDir).toBe('./dist');
    expect(options.siteTitle).toBe('My Static Site');
  });

  it('parses --content and --output flags', () => {
    const options = parseCliArgs(['node', 'ssg', 'build', '--content', 'src', '--output', 'public']);
    expect(options.contentDir).toBe('src');
    expect(options.outputDir).toBe('public');
  });

  it('parses --content= and --output= syntax', () => {
    const options = parseCliArgs(['node', 'ssg', 'build', '--content=content', '--output=build']);
    expect(options.contentDir).toBe('content');
    expect(options.outputDir).toBe('build');
  });

  it('supports --help', () => {
    const options = parseCliArgs(['node', 'ssg', '--help']);
    expect(options.help).toBe(true);
  });

  it('throws on unknown arguments', () => {
    expect(() => parseCliArgs(['node', 'ssg', 'build', '--bogus'])).toThrow(/Unknown argument/);
  });
});

describe('run', () => {
  let tmp: string;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(() => {
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it('builds a site and returns exit code 0', async () => {
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    fs.mkdirSync(contentDir, { recursive: true });
    fs.writeFileSync(path.join(contentDir, 'post.md'), '---\ntitle: Post\ndate: 2024-01-01\n---\n\n# Post body');

    const code = await run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir]);

    expect(code).toBe(0);
    expect(fs.existsSync(path.join(outputDir, 'post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('prints usage and returns exit code 1 for an unknown argument', async () => {
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    const code = await run(['node', 'ssg', 'build', '--nope']);
    expect(code).toBe(1);
    consoleError.mockRestore();
  });

  it('prints help and returns exit code 0 for --help', async () => {
    const consoleLog = jest.spyOn(console, 'log').mockImplementation(() => undefined);
    const code = await run(['node', 'ssg', '--help']);
    expect(code).toBe(0);
    consoleLog.mockRestore();
  });
});
