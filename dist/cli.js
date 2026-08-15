#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseArgs = parseArgs;
exports.run = run;
exports.main = main;
const site_1 = require("./site");
function parseArgs(argv) {
    const args = argv.slice(2);
    const options = {};
    for (let i = 0; i < args.length; i += 1) {
        const arg = args[i];
        if (arg === '--content' || arg === '-c') {
            options.content = args[++i];
        }
        else if (arg === '--output' || arg === '-o') {
            options.output = args[++i];
        }
        else if (arg.startsWith('--content=')) {
            options.content = arg.slice('--content='.length);
        }
        else if (arg.startsWith('--output=')) {
            options.output = arg.slice('--output='.length);
        }
        else if (!arg.startsWith('-')) {
            options.command = arg;
        }
    }
    return options;
}
function run(argv) {
    const options = parseArgs(argv);
    if (options.command !== 'build') {
        throw new Error('Unknown command. Usage: ssg build [--content <dir>] [--output <dir>]');
    }
    return (0, site_1.buildSite)({
        contentDir: options.content || './content',
        outputDir: options.output || './dist',
    });
}
function main(argv = process.argv) {
    const options = parseArgs(argv);
    if (options.command !== 'build') {
        console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
        process.exitCode = 1;
        return;
    }
    const result = (0, site_1.buildSite)({
        contentDir: options.content || './content',
        outputDir: options.output || './dist',
    });
    console.log(`Built ${result.posts.length} page(s) into ${options.output || './dist'}`);
}
if (require.main === module) {
    main();
}
