#!/usr/bin/env node

/**
 * Static site generator CLI.
 *
 *   npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]
 */

import path from 'path';

import { buildSite } from './site';
import { DEFAULT_TEMPLATES_DIR } from './templates';

const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';

export const USAGE = `Usage: ssg build [options]

Options:
  --content <dir>    Directory containing Markdown files (default: ${DEFAULT_CONTENT_DIR})
  --output <dir>     Directory where the site is written (default: ${DEFAULT_OUTPUT_DIR})
  --templates <dir>  Directory containing templates, layouts and partials (default: ${DEFAULT_TEMPLATES_DIR})
  -h, --help         Show this help message`;

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  help: boolean;
}

/** Parse raw CLI arguments (excluding node and the script path). */
export function parseArgs(argv: string[]): CliOptions {
  let command = '';
  let contentDir = path.resolve(DEFAULT_CONTENT_DIR);
  let outputDir = path.resolve(DEFAULT_OUTPUT_DIR);
  let templatesDir = path.resolve(DEFAULT_TEMPLATES_DIR);
  let help = false;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === 'build') {
      command = 'build';
    } else if (arg === '--content' || arg === '-c') {
      const value = argv[i + 1];
      if (value && !value.startsWith('--')) {
        contentDir = path.resolve(value);
        i += 1;
      }
    } else if (arg === '--output' || arg === '-o') {
      const value = argv[i + 1];
      if (value && !value.startsWith('--')) {
        outputDir = path.resolve(value);
        i += 1;
      }
    } else if (arg === '--templates' || arg === '-t') {
      const value = argv[i + 1];
      if (value && !value.startsWith('--')) {
        templatesDir = path.resolve(value);
        i += 1;
      }
    } else if (arg === '--help' || arg === '-h') {
      help = true;
    }
  }

  return { command, contentDir, outputDir, templatesDir, help };
}

/**
 * Run the CLI. Returns the process exit code.
 * The exported signature accepts the raw process.argv so it can be
 * driven from tests.
 */
export function main(argv: string[]): number {
  const options = parseArgs(argv.slice(2));

  if (options.help) {
    console.log(USAGE);
    return 0;
  }

  if (options.command !== 'build') {
    console.error(USAGE);
    return 1;
  }

  const pages = buildSite({
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templatesDir: options.templatesDir,
  });

  console.log(
    `Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${options.outputDir}`
  );
  return 0;
}

// Allow the module to be imported (e.g. by tests) without executing.
if (require.main === module) {
  process.exitCode = main(process.argv);
}
