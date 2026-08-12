import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('parses the build command with defaults', () => {
    const { command, options, help } = parseArgs(['build']);
    expect(command).toBe('build');
    expect(options.contentDir).toBeUndefined();
    expect(options.outputDir).toBeUndefined();
    expect(help).toBe(false);
  });

  it('parses --content and --output flags', () => {
    const { command, options } = parseArgs(['build', '--content', 'src/pages', '--output', 'public']);
    expect(command).toBe('build');
    expect(options.contentDir).toBe('src/pages');
    expect(options.outputDir).toBe('public');
  });

  it('defaults the command to build when omitted', () => {
    const { command } = parseArgs(['--content', 'pages']);
    expect(command).toBe('build');
  });

  it('flags help when --help is passed', () => {
    const { help } = parseArgs(['build', '--help']);
    expect(help).toBe(true);
  });
});
