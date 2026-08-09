#!/usr/bin/env node
import { parseArgs } from './cli';
import { Generator } from './generator';
import { startDevServer } from './server';

const options = parseArgs(process.argv);

if (options.command === 'serve') {
  startDevServer(options);
} else {
  const generator = new Generator(options);
  generator.generate();
  console.log('Site generated successfully!');
}
