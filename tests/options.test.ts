import { parseBuildOptions } from '../src/options.js';

describe('parseBuildOptions', () => {
  it('accepts content and output directories', () => {
    expect(parseBuildOptions(['--content', 'posts', '--output', 'public'])).toEqual({
      contentDir: 'posts',
      outputDir: 'public',
    });
  });

  it('rejects incomplete and unknown options', () => {
    expect(() => parseBuildOptions(['--content'])).toThrow('Missing value for --content');
    expect(() => parseBuildOptions(['--unknown'])).toThrow('Unknown option: --unknown');
  });
});
