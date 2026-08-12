import { parseArgs, CliOptions } from '../src/cli';

describe('parseArgs', () => {
  it('defaults command to build with default directories', () => {
    const { command, options } = parseArgs([]);
    expect(command).toBe('build');
    expect(options).toEqual({
      contentDir: 'content',
      outputDir: 'dist',
      templatesDir: 'templates',
    } as CliOptions);
  });

  it('parses an explicit command with options', () => {
    const { command, options } = parseArgs([
      'build',
      '--content',
      'src/content',
      '--output',
      'public',
    ]);
    expect(command).toBe('build');
    expect(options.contentDir).toBe('src/content');
    expect(options.outputDir).toBe('public');
  });

  it('parses the templates directory option', () => {
    const { options } = parseArgs(['build', '--templates', 'themes/base']);
    expect(options.templatesDir).toBe('themes/base');

    const short = parseArgs(['build', '-t', 'custom']);
    expect(short.options.templatesDir).toBe('custom');
  });

  it('parses shorthand flags', () => {
    const { options } = parseArgs(['-c', 'c', '-o', 'o']);
    expect(options.contentDir).toBe('c');
    expect(options.outputDir).toBe('o');
  });

  it('treats a leading non-option word as the command', () => {
    const { command } = parseArgs(['serve']);
    expect(command).toBe('serve');
  });

  it('throws on unknown options', () => {
    expect(() => parseArgs(['build', '--bogus'])).toThrow(/unknown argument/);
  });

  it('throws when a value is missing for an option', () => {
    expect(() => parseArgs(['build', '--content'])).toThrow(/missing value/);
  });
});
