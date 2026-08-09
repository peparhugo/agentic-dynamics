import { describe, it, expect } from 'vitest';
import { parseArgs } from '../src/cli';

function args(...flags: string[]): string[] {
  return ['node', 'ssg', '-s', 'source', '-t', 'templates', '-o', 'output', ...flags];
}

describe('CLI flag behavior', () => {
  it('parses required short options', () => {
    const config = parseArgs(['node', 'ssg', '-s', 'src', '-t', 'tmpl', '-o', 'dist']);
    expect(config.sourceDir).toBe('src');
    expect(config.templateDir).toBe('tmpl');
    expect(config.outputDir).toBe('dist');
  });

  it('parses required long options', () => {
    const config = parseArgs([
      'node', 'ssg',
      '--source', 'content',
      '--templates', 'theme',
      '--output', 'public',
    ]);
    expect(config.sourceDir).toBe('content');
    expect(config.templateDir).toBe('theme');
    expect(config.outputDir).toBe('public');
  });

  it('dev mode defaults to false', () => {
    const config = parseArgs(args());
    expect(config.devMode).toBe(false);
  });

  it('enables dev mode with -d', () => {
    const config = parseArgs(args('-d'));
    expect(config.devMode).toBe(true);
  });

  it('enables dev mode with --dev', () => {
    const config = parseArgs(args('--dev'));
    expect(config.devMode).toBe(true);
  });

  it('default port is 3000', () => {
    const config = parseArgs(args());
    expect(config.port).toBe(3000);
  });

  it('parses port with -p', () => {
    const config = parseArgs(args('-p', '8080'));
    expect(config.port).toBe(8080);
  });

  it('parses port with --port', () => {
    const config = parseArgs(args('--port', '4000'));
    expect(config.port).toBe(4000);
  });

  it('includeDrafts defaults to false', () => {
    const config = parseArgs(args());
    expect(config.includeDrafts).toBe(false);
  });

  it('sets includeDrafts with --drafts', () => {
    const config = parseArgs(args('--drafts'));
    expect(config.includeDrafts).toBe(true);
  });

  it('default site title is "My Site"', () => {
    const config = parseArgs(args());
    expect(config.siteTitle).toBe('My Site');
  });

  it('parses site title with --title', () => {
    const config = parseArgs(args('--title', 'My Blog'));
    expect(config.siteTitle).toBe('My Blog');
  });

  it('default site URL is http://localhost:3000', () => {
    const config = parseArgs(args());
    expect(config.siteUrl).toBe('http://localhost:3000');
  });

  it('parses site URL with --url', () => {
    const config = parseArgs(args('--url', 'https://example.com'));
    expect(config.siteUrl).toBe('https://example.com');
  });

  it('throws on missing required source option', () => {
    expect(() =>
      parseArgs(['node', 'ssg', '-t', 't', '-o', 'o'])
    ).toThrow('Missing required option');
  });

  it('throws on missing required templates option', () => {
    expect(() =>
      parseArgs(['node', 'ssg', '-s', 's', '-o', 'o'])
    ).toThrow('Missing required option');
  });

  it('throws on missing required output option', () => {
    expect(() =>
      parseArgs(['node', 'ssg', '-s', 's', '-t', 't'])
    ).toThrow('Missing required option');
  });
});
