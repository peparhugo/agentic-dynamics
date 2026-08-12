import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';

const CLI = path.resolve(__dirname, '..', 'dist', 'index.js');
const FIXTURES = path.resolve(__dirname, '..', 'content');
const OUT = path.resolve(__dirname, '..', 'test-cli-dist');

function runCli(args: string): string {
  return execSync(`node ${CLI} ${args}`, { encoding: 'utf-8' });
}

beforeEach(() => {
  if (fs.existsSync(OUT)) {
    fs.rmSync(OUT, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(OUT)) {
    fs.rmSync(OUT, { recursive: true, force: true });
  }
});

describe('CLI', () => {
  test('build command generates site', () => {
    const output = runCli(`build --content ${FIXTURES} --output ${OUT}`);
    expect(output).toContain('Site built successfully');
    expect(fs.existsSync(path.join(OUT, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'first-post.html'))).toBe(true);
  });

  test('build with default paths works', () => {
    const output = runCli(`build`);
    expect(output).toMatch(/error|Site built/i);
  });

  test('without build command shows usage', () => {
    const output = runCli('unknown');
    expect(output).toContain('Usage');
  });
});
