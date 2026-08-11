#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const parser_1 = require("./parser");
const generator_1 = require("./generator");
function parseArgs(args) {
    let content = 'content';
    let output = 'dist';
    let templates = 'templates';
    let i = 0;
    while (i < args.length) {
        if (args[i] === '--content' && i + 1 < args.length) {
            content = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            output = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--templates' && i + 1 < args.length) {
            templates = args[i + 1];
            i += 2;
        }
        else {
            i++;
        }
    }
    return { content, output, templates };
}
const command = process.argv[2];
if (command !== 'build') {
    console.log('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
    process.exit(command ? 1 : 0);
}
const { content, output, templates } = parseArgs(process.argv.slice(3));
const pages = (0, parser_1.parseDirectory)(content);
(0, generator_1.generateSite)(pages, output, templates);
console.log(`Site generated in ${output} (${pages.length} pages)`);
//# sourceMappingURL=cli.js.map