#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const yargs_1 = __importDefault(require("yargs"));
const helpers_1 = require("yargs/helpers");
const path_1 = __importDefault(require("path"));
const files_1 = require("./files");
const page_1 = require("./page");
const generator_1 = require("./generator");
async function build(contentDir, outputDir) {
    console.log(`Reading markdown files from: ${contentDir}`);
    const files = await (0, files_1.readMarkdownFiles)(contentDir);
    if (files.length === 0) {
        console.log('No markdown files found.');
        return;
    }
    console.log(`Found ${files.length} markdown file(s).`);
    const pages = [];
    for (const file of files) {
        const page = await (0, page_1.processMarkdownFile)(file.name, file.content);
        pages.push(page);
        await (0, generator_1.generatePageHtml)(page, outputDir);
        console.log(`✓ Generated ${page.slug}.html`);
    }
    await (0, generator_1.generateIndexHtml)(pages, outputDir);
    console.log(`✓ Generated index.html`);
    console.log(`\nBuild complete! Output: ${outputDir}`);
}
(0, yargs_1.default)((0, helpers_1.hideBin)(process.argv))
    .command('build', 'Build the static site', (yargs) => {
    return yargs
        .option('content', {
        alias: 'c',
        describe: 'Content directory',
        type: 'string',
        default: './content'
    })
        .option('output', {
        alias: 'o',
        describe: 'Output directory',
        type: 'string',
        default: './dist'
    });
}, async (argv) => {
    const contentDir = path_1.default.resolve(argv.content);
    const outputDir = path_1.default.resolve(argv.output);
    try {
        await build(contentDir, outputDir);
    }
    catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
})
    .demandCommand()
    .strict()
    .help()
    .parse();
//# sourceMappingURL=index.js.map