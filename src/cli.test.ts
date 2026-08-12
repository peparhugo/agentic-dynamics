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

describe('parseArgs serve', () => {
  it('parses the serve command with default port and host', () => {
    const args = parseArgs(['serve']);
    expect(args.command).toBe('serve');
    expect(args.port).toBe(3000);
    expect(args.host).toBe('localhost');
  });

  it('parses --port and --host values', () => {
    const args = parseArgs(['serve', '--port', '8080', '--host', '0.0.0.0']);
    expect(args.command).toBe('serve');
    expect(args.port).toBe(8080);
    expect(args.host).toBe('0.0.0.0');
  });

  it('throws on an invalid port', () => {
    expect(() => parseArgs(['serve', '--port', 'not-a-number'])).toThrow('valid port');
  });

  it('throws on an out-of-range port', () => {
    expect(() => parseArgs(['serve', '--port', '70000'])).toThrow('valid port');
  });

  it('throws when --port is missing its value', () => {
    expect(() => parseArgs(['serve', '--port'])).toThrow('requires a value');
  });
});
