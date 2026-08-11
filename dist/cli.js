#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const generator_1 = require("./generator");
const server_1 = require("./server");
const program = new commander_1.Command();
program
    .name('ssg')
    .description('Static site generator')
    .version('1.0.0');
program
    .command('build')
    .description('Build the static site')
    .option('--content <dir>', 'Content directory', './content')
    .option('--output <dir>', 'Output directory', './dist')
    .option('--templates <dir>', 'Templates directory', './templates')
    .action((options) => {
    try {
        (0, generator_1.buildSite)(options.content, options.output, options.templates);
        console.log(`Site built successfully in ${options.output}`);
    }
    catch (err) {
        console.error('Error:', err.message);
        process.exit(1);
    }
});
program
    .command('serve')
    .description('Start dev server with live reload')
    .option('--content <dir>', 'Content directory', './content')
    .option('--output <dir>', 'Output directory', './dist')
    .option('--templates <dir>', 'Templates directory', './templates')
    .option('--port <port>', 'Port to listen on', '3000')
    .action(async (options) => {
    try {
        await (0, server_1.startDevServer)({
            content: options.content,
            output: options.output,
            templates: options.templates,
            port: parseInt(options.port, 10),
        });
    }
    catch (err) {
        console.error('Error:', err.message);
        process.exit(1);
    }
});
program.parse(process.argv);
//# sourceMappingURL=cli.js.map