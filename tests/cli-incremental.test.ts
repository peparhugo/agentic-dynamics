import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { createCli, run } from '../src/cli';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

describe('ssg build --incremental / --clean CLI flags', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-cli-inc-content-');
    outputDir = makeTempDir('ssg-cli-inc-output-');
    templatesDir = makeTempDir('ssg-cli-inc-templates-');

    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    writeFile(
      path.join(contentDir, 'hello.md'),
      `---\ntitle: Hello\n---\nHello from the CLI incremental test.\n`
    );

    logSpy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
    logSpy.mockRestore();
  });

  const args = (...extra: string[]) => [
    'node',
    'ssg',
    'build',
    '--content',
    contentDir,
    '--output',
    outputDir,
    '--templates',
    templatesDir,
    ...extra,
  ];

  it('registers --incremental and --clean options on the build command', () => {
    const program = createCli();
    const buildCommand = program.commands.find((cmd) => cmd.name() === 'build');
    const optionFlags = buildCommand!.options.map((opt) => opt.long);

    expect(optionFlags).toEqual(expect.arrayContaining(['--incremental', '--clean']));
  });

  it('creates a cache manifest and reports build stats when --incremental is passed', () => {
    run(args('--incremental'));

    expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(true);
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('1 built, 0 skipped'));
  });

  it('skips the unchanged page on a second --incremental run', () => {
    run(args('--incremental'));
    logSpy.mockClear();

    run(args('--incremental'));

    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('0 built, 1 skipped'));
  });

  it('forces a full rebuild when --clean is passed alongside --incremental', () => {
    run(args('--incremental'));
    logSpy.mockClear();

    run(args('--incremental', '--clean'));

    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('1 built, 0 skipped'));
  });

  it('does not write a cache manifest when --incremental is omitted', () => {
    run(args());
    expect(fs.existsSync(path.join(outputDir, '.ssg-cache.json'))).toBe(false);
  });
});
