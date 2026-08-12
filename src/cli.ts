#!/usr/bin/env node
import { build, BuildOptions } from './ssg';

const DEFAULT_COMMAND = 'build';

function printUsage(): void {
  console.log(`Usage:
  ssg build [options]

Options:
  --content <dir>     Source directory for Markdown files (default: ./content)
  --output <dir>      Output directory for generated HTML (default: ./dist)
  --templates <dir>   Directory for Handlebars templates (default: ./templates)
  --help              Show this help`);
}

function parseArgs(argv: string[]): { command: string; options: BuildOptions; help: boolean } {
  const options: BuildOptions = {};
  let help = false;
  let command = DEFAULT_COMMAND;

  let idx = 0;
  while (idx < argv.length) {
    const arg = argv[idx];
    switch (arg) {
      case '--help':
      case '-h':
        help = true;
        idx += 1;
        break;
      case '--content':
        options.contentDir = argv[idx + 1];
        idx += 2;
        break;
      case '--output':
        options.outputDir = argv[idx + 1];
        idx += 2;
        break;
      case '--templates':
        options.templateDir = argv[idx + 1];
        idx += 2;
        break;
      default:
        if (arg.startsWith('-')) {
          idx += 1;
        } else {
          command = arg;
          idx += 1;
        }
    }
  }

  return { command, options, help };
}

function main(): void {
  const { command, options, help } = parseArgs(process.argv.slice(2));

  if (help || command !== 'build') {
    printUsage();
    if (command !== 'build') {
      process.exitCode = 1;
    }
    return;
  }

  const pages = build(options);
  console.log(`Generated ${pages.length} page(s) into ${options.outputDir ?? './dist'}`);
}

if (require.main === module) {
  main();
}

export { parseArgs, main };
