import { promises as fs } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { parseArgs, run, printHelp, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR } from '../src/cli';
import { buildSite } from '../src/generator';

jest.mock('../src/generator', () => ({
  buildSite: jest.fn()
}));

const mockedBuildSite = buildSite as jest.Mock;

describe('parseArgs', () => {
  it('defaults content to ./content and output to ./dist', () => {
    const { command, options } = parseArgs(['build']);
    expect(command).toBe('build');
    expect(options.contentDir.endsWith(`/${DEFAULT_CONTENT_DIR}`)).toBe(true);
    expect(options.outputDir.endsWith(`/${DEFAULT_OUTPUT_DIR}`)).toBe(true);
  });

  it('parses --content and --output flags', () => {
    const { options } = parseArgs(['build', '--content', 'src/md', '--output', 'public']);
    expect(options.contentDir.endsWith('/src/md')).toBe(true);
    expect(options.outputDir.endsWith('/public')).toBe(true);
  });

  it('parses equals-style options', () => {
    const { options } = parseArgs(['build', '--content=src/md', '--output=public']);
    expect(options.contentDir.endsWith('/src/md')).toBe(true);
    expect(options.outputDir.endsWith('/public')).toBe(true);
  });

  it('sets command to help for --help', () => {
    const { command } = parseArgs(['--help']);
    expect(command).toBe('help');
  });
});

describe('printHelp', () => {
  it('mentions build, content and output', () => {
    const help = printHelp();
    expect(help).toContain('ssg build');
    expect(help).toContain('--content');
    expect(help).toContain('--output');
  });
});

describe('run', () => {
  it('runs the build with parsed options', async () => {
    mockedBuildSite.mockResolvedValue([{ slug: 'a' }]);
    const out = join(tmpdir(), `ssg-out-${Date.now()}`);

    const log = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    await run(['build', '--content', 'x', '--output', out]);

    expect(mockedBuildSite).toHaveBeenCalledTimes(1);
    expect(mockedBuildSite.mock.calls[0][0].outputDir.endsWith(out)).toBe(true);
    expect(log).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
    log.mockRestore();
  });

  it('prints help for the help command without building', async () => {
    const log = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    await run(['--help']);
    expect(mockedBuildSite).not.toHaveBeenCalled();
    expect(log).toHaveBeenCalledWith(expect.stringContaining('ssg build'));
    log.mockRestore();
  });

  it('rejects unknown commands', async () => {
    await expect(run(['serve'])).rejects.toThrow('Unknown command');
  });
});
