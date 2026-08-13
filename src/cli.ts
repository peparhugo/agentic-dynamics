#!/usr/bin/env node

import { buildSite } from './index';
import { serveSite } from './server';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
}

const USAGE = `Usage: ssg <command> [options]

Commands:
  build             Generate the static site
  serve             Build and serve the site with live reload

Options:
  --content <dir>  Markdown content directory (default: ./content)
  --output <dir>   Generated site directory (default: ./dist)
  --templates <dir> Template directory (default: ./templates)
  --port <number>   Development server port (default: 3000)
  -h, --help       Show this help message`;

function parseArguments(args: string[]): { command: 'build' | 'serve'; options: CliOptions } | null {
  if (args.includes('--help') || args.includes('-h')) {
    console.log(USAGE);
    return null;
  }
  if (args[0] !== 'build' && args[0] !== 'serve') {
    throw new Error(`Unknown command${args[0] ? `: ${args[0]}` : ''}\n\n${USAGE}`);
  }

  const options: CliOptions = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if (option !== '--content' && option !== '--output' && option !== '--templates' && option !== '--port') {
      throw new Error(`Unknown option: ${option}\n\n${USAGE}`);
    }
    if (!value || value.startsWith('-')) {
      throw new Error(`Missing value for ${option}\n\n${USAGE}`);
    }
    if (option === '--port') {
      if (args[0] !== 'serve') throw new Error(`Unknown option: ${option}\n\n${USAGE}`);
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error(`Invalid port: ${value}\n\n${USAGE}`);
      }
      options.port = port;
    } else if (option === '--content') {
      options.contentDir = value;
    } else if (option === '--output') {
      options.outputDir = value;
    } else {
      options.templatesDir = value;
    }
    index += 1;
  }
  return { command: args[0], options };
}

export async function run(args: string[]): Promise<void> {
  const parsed = parseArguments(args);
  if (!parsed) return;
  if (parsed.command === 'serve') {
    const server = await serveSite(parsed.options);
    console.log(`Serving ${parsed.options.outputDir ?? './dist'} at http://localhost:${server.port}`);
    return;
  }
  const pages = await buildSite(parsed.options);
  console.log(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
