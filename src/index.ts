#!/usr/bin/env node

import { generateSite } from './generator';

interface Options {
  content: string;
  output: string;
  templates?: string;
}

function parseArgs(args: string[]): { command: string; options: Options } | null {
  const command = args[2];
  if (command !== 'build') {
    return null;
  }

  const options: Options = { content: './content', output: './dist' };

  let i = 3;
  while (i < args.length) {
    if (args[i] === '--content' && i + 1 < args.length) {
      options.content = args[i + 1];
      i += 2;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      options.output = args[i + 1];
      i += 2;
    } else if (args[i] === '--templates' && i + 1 < args.length) {
      options.templates = args[i + 1];
      i += 2;
    } else {
      i += 1;
    }
  }

  return { command, options };
}

const parsed = parseArgs(process.argv);
if (!parsed) {
  console.error('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  process.exit(1);
}

const count = generateSite(parsed.options.content, parsed.options.output, parsed.options.templates);
process.exit(count > 0 ? 0 : 1);
