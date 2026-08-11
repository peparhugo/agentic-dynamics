#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const yargs_1 = __importDefault(require("yargs"));
const helpers_1 = require("yargs/helpers");
const ssg_1 = require("./ssg");
(0, yargs_1.default)((0, helpers_1.hideBin)(process.argv))
    .scriptName('ssg')
    .command('build', 'Build the static site', (yargs) => yargs
    .option('content', {
    type: 'string',
    default: './content',
    describe: 'Content directory with Markdown files',
})
    .option('output', {
    type: 'string',
    default: './dist',
    describe: 'Output directory for generated HTML',
})
    .option('templates', {
    type: 'string',
    default: './templates',
    describe: 'Template directory',
}), (argv) => {
    (0, ssg_1.build)({
        contentDir: argv.content,
        outputDir: argv.output,
        templateDir: argv.templates,
    });
})
    .demandCommand(1, 'Please specify a command: build')
    .help()
    .parse();
//# sourceMappingURL=index.js.map