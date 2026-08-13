import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { run } from '../src/cli';

function makeTmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-test-'));
}

describe('ssg build CLI', () => {
  let contentDir: string;
  let outputDir: string;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: CLI Page\n---\nHello from the CLI'
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

    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
  });

  it('builds the site using a custom --templates directory', () => {
    const templatesDir = makeTmpDir();
    fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<div class="custom-layout">{{{body}}}</div>'
    );

    try {
      run([
        'node',
        'ssg',
        'build',
        '--content',
        contentDir,
        '--output',
        outputDir,
        '--templates',
        templatesDir,
      ]);

      const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
      expect(html).toContain('class="custom-layout"');
      expect(html).toContain('CLI Page');
    } finally {
      fs.rmSync(templatesDir, { recursive: true, force: true });
    }
  });
});
