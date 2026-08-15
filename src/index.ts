#!/usr/bin/env node

import { parseArgs } from './cli.js';
import { generate } from './generator.js';

const args = parseArgs(process.argv.slice(2));

if (args.command === 'build') {
  generate({
    contentDir: args.contentDir,
    outputDir: args.outputDir
  }).catch(error => {
    console.error('Error:', error.message);
    process.exit(1);
  });
} else {
  console.error('Unknown command:', args.command);
  process.exit(1);
}
