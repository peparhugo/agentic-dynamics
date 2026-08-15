import { parseArgs } from '../cli.js';

describe('CLI argument parser', () => {
  it('should parse build command', () => {
    const result = parseArgs(['build']);
    expect(result.command).toBe('build');
    expect(result.contentDir).toBe('./content');
    expect(result.outputDir).toBe('./dist');
  });

  it('should parse --content option', () => {
    const result = parseArgs(['build', '--content', './my-content']);
    expect(result.contentDir).toBe('./my-content');
  });

  it('should parse --output option', () => {
    const result = parseArgs(['build', '--output', './my-dist']);
    expect(result.outputDir).toBe('./my-dist');
  });

  it('should parse both --content and --output options', () => {
    const result = parseArgs(['build', '--content', './src', '--output', './build']);
    expect(result.contentDir).toBe('./src');
    expect(result.outputDir).toBe('./build');
  });

  it('should handle --help flag', () => {
    const result = parseArgs(['--help']);
    expect(result.help).toBe(true);
  });

  it('should default to null command if none provided', () => {
    const result = parseArgs([]);
    expect(result.command).toBeNull();
  });

  it('should handle options in any order', () => {
    const result = parseArgs(['--output', './dist', 'build', '--content', './content']);
    expect(result.command).toBe('build');
    expect(result.outputDir).toBe('./dist');
    expect(result.contentDir).toBe('./content');
  });

  it('should handle missing values for options', () => {
    const result = parseArgs(['build', '--content']);
    expect(result.contentDir).toBe('./content');
  });

  it('should parse --templates option', () => {
    const result = parseArgs(['build', '--templates', './my-templates']);
    expect(result.templatesDir).toBe('./my-templates');
  });

  it('should default templatesDir to ./templates', () => {
    const result = parseArgs(['build']);
    expect(result.templatesDir).toBe('./templates');
  });

  it('should parse --templates with other options', () => {
    const result = parseArgs(['build', '--content', './src', '--output', './dist', '--templates', './tmpl']);
    expect(result.contentDir).toBe('./src');
    expect(result.outputDir).toBe('./dist');
    expect(result.templatesDir).toBe('./tmpl');
  });

  it('should handle missing value for --templates option', () => {
    const result = parseArgs(['build', '--templates']);
    expect(result.templatesDir).toBe('./templates');
  });
});
