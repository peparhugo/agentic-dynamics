import { parseArgs, HelpError } from '../src/cli';

describe('parseArgs', () => {
  it('defaults to build with ./content and ./dist', () => {
    const { command, options } = parseArgs([]);
    expect(command).toBe('build');
    expect(options.contentDir).toBe('content');
    expect(options.outputDir).toBe('dist');
  });

  it('parses --content and --output', () => {
    const { command, options } = parseArgs([
      'build',
      '--content',
      'pages',
      '--output',
      'public',
    ]);
    expect(command).toBe('build');
    expect(options.contentDir).toBe('pages');
    expect(options.outputDir).toBe('public');
  });

  it('supports = syntax', () => {
    const { options } = parseArgs(['build', '--content=posts', '--output=site']);
    expect(options.contentDir).toBe('posts');
    expect(options.outputDir).toBe('site');
  });

  it('throws for unknown arguments', () => {
    expect(() => parseArgs(['build', '--bogus'])).toThrow('unknown argument');
  });

  it('throws for an unknown command', () => {
    expect(() => parseArgs(['serve'])).toThrow('unknown command');
  });

  it('throws HelpError for --help', () => {
    expect(() => parseArgs(['--help'])).toThrow(HelpError);
  });
});
