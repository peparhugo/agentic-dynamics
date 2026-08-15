#!/usr/bin/env node
import { build } from './ssg';

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
}

export function parseArgs(argv: string[]): CliOptions {
  const args = argv.slice(2);
  let command = 'build';
  let contentDir = './content';
  let outputDir = './dist';
  const positionals: string[] = [];

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content' || arg === '-c') {
      contentDir = args[++i] ?? contentDir;
    } else if (arg === '--output' || arg === '-o') {
      outputDir = args[++i] ?? outputDir;
    } else if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
    } else if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
    } else if (!arg.startsWith('-')) {
      positionals.push(arg);
    }
  }

  if (positionals.length > 0) {
    command = positionals[0];
  }

  return { command, contentDir, outputDir };
}

export function run(argv: string[]): number {
  const opts = parseArgs(argv);

  if (opts.command !== 'build') {
    console.error(`Unknown command: ${opts.command}`);
    return 1;
  }

  try {
    const result = build({ contentDir: opts.contentDir, outputDir: opts.outputDir });
    console.log(`Generated ${result.pages.length} page(s) in ${opts.outputDir}`);
    return 0;
  } catch (err) {
    console.error((err as Error).message);
    return 1;
  }
}

if (require.main === module) {
  process.exit(run(process.argv));
}
