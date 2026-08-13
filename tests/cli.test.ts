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

  it('rejects unsupported commands and incomplete options', () => {
    expect(() => parseArgs(['serve'])).toThrow('Usage:');
    expect(() => parseArgs(['build', '--content'])).toThrow('Invalid option: --content');
    expect(() => parseArgs(['build', '--unknown', 'value'])).toThrow('Invalid option: --unknown');
  });
});
