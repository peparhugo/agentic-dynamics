#!/usr/bin/env node

import { parseArgs } from './cli.js';
import { generate } from './generator.js';
import { serve } from './serve.js';

const args = parseArgs(process.argv.slice(2));

if (args.command === 'build') {
  generate({
    contentDir: args.contentDir,
    outputDir: args.outputDir,
    incremental: args.incremental,
    clean: args.clean
  }).catch(error => {
    console.error('Error:', error.message);
    process.exit(1);
  });
} else if (args.command === 'serve') {
  serve({
    contentDir: args.contentDir,
    outputDir: args.outputDir,
    port: args.port
  }).catch(error => {
    console.error('Error:', error.message);
    process.exit(1);
  });
  // Keep the process running for the dev server
} else {
  console.error('Unknown command:', args.command);
  process.exit(1);
}
