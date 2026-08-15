import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { run } from './cli';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('ssg build CLI', () => {
  let contentDir: string;
  let outputDir: string;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-cli-content-');
    outputDir = makeTmpDir('ssg-cli-output-');
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    logSpy.mockRestore();
  });

  it('builds a site using the --content and --output options', () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: CLI Page\n---\n\nHello from the CLI.'
    );

    run(['node', 'ssg', 'build', '--content', contentDir, '--output', outputDir]);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
  });
});
