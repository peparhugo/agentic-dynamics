#!/usr/bin/env node
import { buildSite, BuildResult } from './site';

export interface CliOptions {
  command?: string;
  content?: string;
  output?: string;
  templates?: string;
}

export function parseArgs(argv: string[]): CliOptions {
  const args = argv.slice(2);
  const options: CliOptions = {};

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--content' || arg === '-c') {
      options.content = args[++i];
    } else if (arg === '--output' || arg === '-o') {
      options.output = args[++i];
    } else if (arg === '--templates' || arg === '-t') {
      options.templates = args[++i];
    } else if (arg.startsWith('--content=')) {
      options.content = arg.slice('--content='.length);
    } else if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length);
    } else if (arg.startsWith('--templates=')) {
      options.templates = arg.slice('--templates='.length);
    } else if (!arg.startsWith('-')) {
      options.command = arg;
    }
  }

  return options;
}

export function run(argv: string[]): BuildResult {
  const options = parseArgs(argv);
  if (options.command !== 'build') {
    throw new Error('Unknown command. Usage: ssg build [--content <dir>] [--output <dir>]');
  }
  return buildSite({
    contentDir: options.content || './content',
    outputDir: options.output || './dist',
    templatesDir: options.templates,
  });
}

export function main(argv: string[] = process.argv): void {
  const options = parseArgs(argv);
  if (options.command !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
    process.exitCode = 1;
    return;
  }
  const result = buildSite({
    contentDir: options.content || './content',
    outputDir: options.output || './dist',
    templatesDir: options.templates,
  });
  console.log(`Built ${result.posts.length} page(s) into ${options.output || './dist'}`);
}

if (require.main === module) {
  main();
}
