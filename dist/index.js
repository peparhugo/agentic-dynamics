#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const build_1 = require("./build");
const serve_1 = require("./serve");
function parseBuildArgs(argv) {
    const contentIdx = argv.indexOf('--content');
    const outputIdx = argv.indexOf('--output');
    const templatesIdx = argv.indexOf('--templates');
    const incremental = argv.includes('--incremental');
    const clean = argv.includes('--clean');
    return {
        contentDir: contentIdx !== -1 ? argv[contentIdx + 1] : './content',
        outputDir: outputIdx !== -1 ? argv[outputIdx + 1] : './dist',
        templatesDir: templatesIdx !== -1 ? argv[templatesIdx + 1] : undefined,
        incremental,
        clean,
    };
}
function parseServeArgs(argv) {
    const buildOptions = parseBuildArgs(argv);
    const portIdx = argv.indexOf('--port');
    const port = portIdx !== -1 ? parseInt(argv[portIdx + 1], 10) : 3000;
    return {
        contentDir: buildOptions.contentDir,
        outputDir: buildOptions.outputDir,
        templatesDir: buildOptions.templatesDir,
        port: isNaN(port) ? 3000 : port,
    };
}
const args = process.argv.slice(2);
const command = args[0];
if (command === 'build') {
    const options = parseBuildArgs(args);
    try {
        const stats = (0, build_1.build)(options);
        const builtMsg = `Pages: ${stats.pagesBuilt} built`;
        const skippedMsg = stats.pagesSkipped > 0 ? `, ${stats.pagesSkipped} skipped (unchanged)` : '';
        const totalMsg = `, ${stats.totalPages} total`;
        console.log(`Site built successfully in ${options.outputDir}`);
        console.log(builtMsg + skippedMsg + totalMsg);
    }
    catch (err) {
        console.error('Error building site:', err.message);
        process.exit(1);
    }
}
else if (command === 'serve') {
    const options = parseServeArgs(args);
    (0, serve_1.serve)(options);
}
else {
    console.log('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean]');
    console.log('       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
    process.exit(0);
}
//# sourceMappingURL=index.js.map