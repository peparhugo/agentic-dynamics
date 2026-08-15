import { spawnSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { main, parseArgs, printHelp } from '../src/cli';

const REPO_ROOT = path.resolve(__dirname, '..');
const CLI_JS = path.join(REPO_ROOT, 'dist', 'cli.js');

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), content);
  }
}

function ensureBuilt(): void {
  if (!fs.existsSync(CLI_JS)) {
    const result = spawnSync('npx', ['tsc'], { cwd: REPO_ROOT, encoding: 'utf8' });
    if (result.status !== 0) {
      throw new Error(`Failed to build TypeScript: ${result.stderr}`);
    }
  }
}

describe('parseArgs', () => {
  it('uses default directories when no options are given', () => {
    const opts = parseArgs(['build']);
    expect(opts.command).toBe('build');
    expect(opts.contentDir).toBe('./content');
    expect(opts.outputDir).toBe('./dist');
  });

  it('parses --content and --output options', () => {
    const opts = parseArgs(['build', '--content', 'posts', '--output', 'public']);
    expect(opts.contentDir).toBe('posts');
    expect(opts.outputDir).toBe('public');
  });

  it('recognizes --help', () => {
    expect(parseArgs(['build', '--help']).command).toBe('help');
    expect(parseArgs(['-h']).command).toBe('help');
  });
});

describe('main', () => {
  it('returns 0 and prints help for --help', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
    const code = main(['--help']);
    spy.mockRestore();
    expect(code).toBe(0);
  });

  it('returns 1 for an unknown command', () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    const code = main(['publish']);
    spy.mockRestore();
    expect(code).toBe(1);
  });

  it('returns 1 when the content directory is missing', () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    const tmp = makeTempDir('ssg-cli-missing-');
    const code = main(['build', '--content', path.join(tmp, 'nope')]);
    spy.mockRestore();
    expect(code).toBe(1);
  });
});

describe('cli binary (npx ssg build)', () => {
  beforeAll(() => {
    ensureBuilt();
  });

  it('generates the site into the output directory', () => {
    const tmp = makeTempDir('ssg-cli-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    writeContent(contentDir, {
      'post.md': '---\ntitle: Post\n---\n\n# Post\n',
    });

    const result = spawnSync(process.execPath, [CLI_JS, 'build', '--content', contentDir, '--output', outputDir], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toContain('Built 1 page');
    expect(fs.existsSync(path.join(outputDir, 'post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.readFileSync(path.join(outputDir, 'post.html'), 'utf8')).toContain('<h1>Post</h1>');
  });

  it('fails with a non-zero exit code for a missing content directory', () => {
    const tmp = makeTempDir('ssg-cli-missing-');
    const result = spawnSync(process.execPath, [CLI_JS, 'build', '--content', path.join(tmp, 'nope')], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('Build failed');
  });

  it('exits 0 with help text for --help', () => {
    const result = spawnSync(process.execPath, [CLI_JS, '--help'], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('npx ssg build');
  });
});
