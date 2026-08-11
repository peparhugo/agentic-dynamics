#!/usr/bin/env node

import { parseDirectory } from './parser';
import { generateSite } from './generator';

function parseArgs(args: string[]): { content: string; output: string } {
  let content = 'content';
  let output = 'dist';
  let i = 0;

  while (i < args.length) {
    if (args[i] === '--content' && i + 1 < args.length) {
      content = args[i + 1];
      i += 2;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      output = args[i + 1];
      i += 2;
    } else {
      i++;
    }
  }

  return { content, output };
}

const command = process.argv[2];
if (command !== 'build') {
  console.log('Usage: npx ssg build [--content <dir>] [--output <dir>]');
  process.exit(command ? 1 : 0);
}

const { content, output } = parseArgs(process.argv.slice(3));

const pages = parseDirectory(content);
generateSite(pages, output);
console.log(`Site generated in ${output} (${pages.length} pages)`);
