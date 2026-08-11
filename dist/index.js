#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const parser_1 = require("./parser");
const generator_1 = require("./generator");
function parseArgs(args) {
    const command = args[0] || 'build';
    let contentDir = './content';
    let outputDir = './dist';
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--content' && i + 1 < args.length) {
            contentDir = args[i + 1];
            i++;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            outputDir = args[i + 1];
            i++;
        }
    }
    return { command, contentDir, outputDir };
}
function main() {
    const args = process.argv.slice(2);
    const { command, contentDir, outputDir } = parseArgs(args);
    if (command !== 'build') {
        console.error(`Unknown command: ${command}`);
        console.error('Usage: npx ssg build [--content <dir>] [--output <dir>]');
        process.exit(1);
    }
    try {
        const parseResult = (0, parser_1.parseFiles)({ contentDir, outputDir });
        (0, generator_1.generateSite)(parseResult, outputDir);
        console.log(`Site generated in ${outputDir}`);
    }
    catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`Error: ${message}`);
        process.exit(1);
    }
}
main();
