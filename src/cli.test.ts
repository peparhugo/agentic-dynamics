import { parseArgs } from './cli';

describe('parseArgs', () => {
  it('uses defaults when no options are given', () => {
    const args = parseArgs(['build']);
    expect(args.command).toBe('build');
    expect(args.contentDir).toBe('content');
    expect(args.outputDir).toBe('dist');
    expect(args.showHelp).toBe(false);
  });

  it('parses --content and --output values', () => {
    const args = parseArgs(['build', '--content', 'src/md', '--output', 'public']);
    expect(args.contentDir).toBe('src/md');
    expect(args.outputDir).toBe('public');
  });

  it('sets the help flag', () => {
    const args = parseArgs(['--help']);
    expect(args.showHelp).toBe(true);
  });

  it('throws on an unknown option', () => {
    expect(() => parseArgs(['--bogus'])).toThrow('Unknown option or command');
  });

  it('throws when an option is missing its value', () => {
    expect(() => parseArgs(['build', '--content'])).toThrow('requires a value');
  });
});
