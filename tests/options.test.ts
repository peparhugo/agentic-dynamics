import { parseBuildOptions, parseServeOptions } from '../src/options.js';

describe('parseBuildOptions', () => {
  it('accepts content and output directories', () => {
    expect(parseBuildOptions(['--content', 'posts', '--output', 'public', '--templates', 'views'])).toEqual({
      contentDir: 'posts',
      outputDir: 'public',
      templatesDir: 'views',
    });
  });

  it('accepts incremental and clean build flags', () => {
    expect(parseBuildOptions(['--incremental', '--clean'])).toEqual({ incremental: true, clean: true });
  });

  it('rejects incomplete and unknown options', () => {
    expect(() => parseBuildOptions(['--content'])).toThrow('Missing value for --content');
    expect(() => parseBuildOptions(['--unknown'])).toThrow('Unknown option: --unknown');
  });
});

describe('parseServeOptions', () => {
  it('accepts a valid port', () => {
    expect(parseServeOptions(['--port', '8080'])).toEqual({ port: 8080 });
  });

  it('rejects invalid ports', () => {
    expect(() => parseServeOptions(['--port', 'zero'])).toThrow('Invalid port: zero');
    expect(() => parseServeOptions(['--port', '65536'])).toThrow('Invalid port: 65536');
  });
});
