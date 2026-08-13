#!/usr/bin/env node

import { buildSite } from './index';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

const USAGE = `Usage: ssg build [options]

Options:
  --content <dir>  Markdown content directory (default: ./content)
  --output <dir>   Generated site directory (default: ./dist)
  --templates <dir> Template directory (default: ./templates)
  -h, --help       Show this help message`;

function parseArguments(args: string[]): CliOptions | null {
  if (args.includes('--help') || args.includes('-h')) {
    console.log(USAGE);
    return null;
  }
  if (args[0] !== 'build') {
    throw new Error(`Unknown command${args[0] ? `: ${args[0]}` : ''}\n\n${USAGE}`);
  }

  const options: CliOptions = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if (option !== '--content' && option !== '--output' && option !== '--templates') {
      throw new Error(`Unknown option: ${option}\n\n${USAGE}`);
    }
    if (!value || value.startsWith('-')) {
      throw new Error(`Missing value for ${option}\n\n${USAGE}`);
    }
    if (option === '--content') {
      options.contentDir = value;
    } else if (option === '--output') {
      options.outputDir = value;
    } else {
      options.templatesDir = value;
    }
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const options = parseArguments(args);
  if (!options) return;
  const pages = await buildSite(options);
  console.log(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
