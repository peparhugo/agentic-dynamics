import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseArgs, run } from '../src/cli';

describe('parseArgs', () => {
  it('parses build command with defaults', () => {
    const opts = parseArgs(['node', 'ssg', 'build']);
    expect(opts.command).toBe('build');
    expect(opts.contentDir).toBe('./content');
    expect(opts.outputDir).toBe('./dist');
  });

  it('parses --content and --output flags', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content', 'src', '--output', 'site']);
    expect(opts.contentDir).toBe('src');
    expect(opts.outputDir).toBe('site');
  });

  it('parses --flag=value syntax', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content=in', '--output=out']);
    expect(opts.contentDir).toBe('in');
    expect(opts.outputDir).toBe('out');
  });

  it('parses serve command with a custom port', () => {
    const opts = parseArgs(['node', 'ssg', 'serve', '--port', '8080']);
    expect(opts.command).toBe('serve');
    expect(opts.port).toBe(8080);
  });

  it('parses --port=value syntax', () => {
    const opts = parseArgs(['node', 'ssg', 'serve', '--port=4000']);
    expect(opts.port).toBe(4000);
  });

  it('defaults serve port to 3000', () => {
    const opts = parseArgs(['node', 'ssg', 'serve']);
    expect(opts.port).toBe(3000);
  });

  it('parses --incremental and --clean flags', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--incremental', '--clean']);
    expect(opts.incremental).toBe(true);
    expect(opts.clean).toBe(true);
  });

  it('defaults incremental and clean to false', () => {
    const opts = parseArgs(['node', 'ssg', 'build']);
    expect(opts.incremental).toBe(false);
    expect(opts.clean).toBe(false);
  });
});

describe('run', () => {
  it('builds the site and returns 0', () => {
    const content = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-content-'));
    const out = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-out-'));
    fs.writeFileSync(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\ndate: 2024-01-01\n---\n# Hello\n'
    );

    const code = run(['node', 'ssg', 'build', '--content', content, '--output', out]);
    expect(code).toBe(0);
    expect(fs.existsSync(path.join(out, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(out, 'hello.html'))).toBe(true);

    fs.rmSync(content, { recursive: true, force: true });
    fs.rmSync(out, { recursive: true, force: true });
  });

  it('returns 1 for an unknown command', () => {
    const code = run(['node', 'ssg', 'deploy']);
    expect(code).toBe(1);
  });

  it('returns 1 when content directory is missing', () => {
    const code = run(['node', 'ssg', 'build', '--content', '/does/not/exist']);
    expect(code).toBe(1);
  });

  it('runs an incremental build via the CLI', () => {
    const content = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-content-'));
    const out = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-out-'));
    fs.writeFileSync(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\ndate: 2024-01-01\n---\n# Hello\n'
    );

    const first = run(['node', 'ssg', 'build', '--incremental', '--content', content, '--output', out]);
    expect(first).toBe(0);
    expect(fs.existsSync(path.join(out, 'hello.html'))).toBe(true);

    const second = run(['node', 'ssg', 'build', '--incremental', '--content', content, '--output', out]);
    expect(second).toBe(0);
    expect(fs.existsSync(path.join(out, '.ssg-cache.json'))).toBe(true);

    fs.rmSync(content, { recursive: true, force: true });
    fs.rmSync(out, { recursive: true, force: true });
  });
});
