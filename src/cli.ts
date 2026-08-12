#!/usr/bin/env node
import path from 'path';
import { buildSite } from './build';

export interface CliArgs {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  showHelp: boolean;
  command: string | undefined;
}

const HELP = `Usage: ssg [command] [options]

Commands:
  build       Generate the site from markdown content (default)

Options:
  --content <dir>    Content directory containing markdown files (default: ./content)
  --output <dir>     Output directory for generated HTML (default: ./dist)
  --templates <dir>  Templates directory with .hbs templates, layouts and partials (default: ./templates)
  -h, --help         Show this help message
`;

export function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    contentDir: 'content',
    outputDir: 'dist',
    templatesDir: 'templates',
    showHelp: false,
    command: undefined,
  };

  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];
    switch (arg) {
      case '-h':
      case '--help':
        args.showHelp = true;
        break;
      case 'build':
        args.command = 'build';
        break;
      case '--content':
      case '--output':
      case '--templates': {
        const next = argv[i + 1];
        if (next === undefined || next.startsWith('-')) {
          throw new Error(`Option ${arg} requires a value`);
        }
        if (arg === '--content') args.contentDir = next;
        else if (arg === '--output') args.outputDir = next;
        else args.templatesDir = next;
        i += 1;
        break;
      }
      default:
        throw new Error(`Unknown option or command: ${arg}`);
    }
    i += 1;
  }

  return args;
}

export function run(argv: string[]): number {
  let args: CliArgs;
  try {
    args = parseArgs(argv);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    console.error(HELP);
    return 1;
  }

  if (args.showHelp) {
    process.stdout.write(HELP);
    return 0;
  }

  const contentDir = path.resolve(process.cwd(), args.contentDir);
  const outputDir = path.resolve(process.cwd(), args.outputDir);
  const templatesDir = path.resolve(process.cwd(), args.templatesDir);

  try {
    const pages = buildSite({ contentDir, outputDir, templatesDir });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${outputDir}`);
    return 0;
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    return 1;
  }
}

if (require.main === module) {
  process.exit(run(process.argv.slice(2)));
}
