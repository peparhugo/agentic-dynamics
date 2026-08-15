#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = void 0;
const yargs_1 = __importDefault(require("yargs"));
const helpers_1 = require("yargs/helpers");
const path_1 = __importDefault(require("path"));
const build_1 = require("./build");
const serve_1 = require("./serve");
var build_2 = require("./build");
Object.defineProperty(exports, "build", { enumerable: true, get: function () { return build_2.build; } });
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
    })
        .option('templates', {
        alias: 't',
        describe: 'Templates directory',
        type: 'string'
    });
}, async (argv) => {
    const contentDir = path_1.default.resolve(argv.content);
    const outputDir = path_1.default.resolve(argv.output);
    const templateDir = argv.templates ? path_1.default.resolve(argv.templates) : undefined;
    try {
        await (0, build_1.build)(contentDir, outputDir, templateDir);
    }
    catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
})
    .command('serve', 'Start a live-reload dev server', (yargs) => {
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
    })
        .option('templates', {
        alias: 't',
        describe: 'Templates directory',
        type: 'string'
    })
        .option('port', {
        alias: 'p',
        describe: 'Port to serve on',
        type: 'number',
        default: 3000
    });
}, async (argv) => {
    const contentDir = path_1.default.resolve(argv.content);
    const outputDir = path_1.default.resolve(argv.output);
    const templateDir = argv.templates ? path_1.default.resolve(argv.templates) : undefined;
    const port = argv.port;
    try {
        console.log('Building initial site...');
        await (0, build_1.build)(contentDir, outputDir, templateDir);
        console.log('\n');
        await (0, serve_1.serve)(outputDir, contentDir, templateDir, port);
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