import { parseArgs } from '../src/cli';

describe('CLI arguments', () => {
  it('parses custom directories', () => {
    expect(parseArgs(['build', '--content', 'posts', '--output', 'public', '--templates', 'views'])).toEqual({
      contentDir: 'posts',
      outputDir: 'public',
      templatesDir: 'views'
    });
  });

  it('uses generator defaults when no options are supplied', () => {
    expect(parseArgs(['build'])).toEqual({});
  });

  it('parses incremental and clean build flags', () => {
    expect(parseArgs(['build', '--incremental', '--clean'])).toEqual({ incremental: true, clean: true });
  });

  it('parses serve options and a custom port', () => {
    expect(parseArgs(['serve', '--port', '4321', '--content', 'pages'])).toEqual({
      port: 4321,
      contentDir: 'pages'
    });
  });

  it('rejects unsupported commands and incomplete options', () => {
    expect(() => parseArgs(['preview'])).toThrow('Usage:');
    expect(() => parseArgs(['build', '--content'])).toThrow('Invalid option: --content');
    expect(() => parseArgs(['build', '--unknown', 'value'])).toThrow('Invalid option: --unknown');
    expect(() => parseArgs(['build', '--port', '4000'])).toThrow('Invalid option: --port');
    expect(() => parseArgs(['serve', '--port', 'invalid'])).toThrow('Invalid port: invalid');
  });
});
