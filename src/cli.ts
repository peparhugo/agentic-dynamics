#!/usr/bin/env node

import { parseMarkdownFiles, generateSite } from './index';

interface CliOptions {
  content: string;
  output: string;
  templates: string;
}

function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = { content: './content', output: './dist', templates: './templates' };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--content' && i + 1 < args.length) {
      options.content = args[i + 1];
      i++;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      options.output = args[i + 1];
      i++;
    } else if (args[i] === '--templates' && i + 1 < args.length) {
      options.templates = args[i + 1];
      i++;
    }
  }

  return options;
}

const args = process.argv.slice(2);

if (args[0] !== 'build') {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  process.exit(1);
}

const options = parseArgs(args.slice(1));

const pages = parseMarkdownFiles(options.content);
generateSite(pages, options.output, options.templates);

console.log(`Generated ${pages.length} page(s) in ${options.output}`);
