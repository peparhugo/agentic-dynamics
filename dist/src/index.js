#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const build_1 = require("./build");
const serve_1 = require("./serve");
const program = new commander_1.Command();
program
    .name('ssg')
    .description('Static site generator — converts Markdown files to HTML');
program
    .command('build')
    .description('Generate the site from Markdown files')
    .option('--content <dir>', 'Content directory containing Markdown files', './content')
    .option('--output <dir>', 'Output directory for generated HTML files', './dist')
    .option('--templates <dir>', 'Templates directory for Handlebars layouts, templates, and partials', './templates')
    .action((options) => {
    try {
        (0, build_1.build)(options.content, options.output, options.templates);
        console.log(`Site built successfully. Output: ${options.output}`);
    }
    catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`Error: ${message}`);
        process.exit(1);
    }
});
program
    .command('serve')
    .description('Start a development server with live reload')
    .option('--content <dir>', 'Content directory containing Markdown files', './content')
    .option('--output <dir>', 'Output directory for generated HTML files', './dist')
    .option('--templates <dir>', 'Templates directory for Handlebars layouts, templates, and partials', './templates')
    .option('--port <port>', 'Port to listen on', '3000')
    .action((options) => {
    (0, serve_1.serve)({
        content: options.content,
        output: options.output,
        templates: options.templates,
        port: parseInt(options.port, 10),
    });
});
program.parse(process.argv);
//# sourceMappingURL=index.js.map