import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { run } from '../src/cli';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('ssg build CLI', () => {
  let contentDir: string;
  let outputDir: string;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-cli-content-');
    outputDir = makeTempDir('ssg-cli-output-');

    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello CLI
date: 2024-06-01
tags: [cli]
---
Hello from the CLI test.
`
    );

    logSpy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    logSpy.mockRestore();
  });

  it('builds the site using --content and --output options', () => {
    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir]);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);

    const pageHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(pageHtml).toContain('Hello CLI');
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
  });
});
