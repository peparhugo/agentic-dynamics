#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const build_1 = require("./build");
function parseArgs(argv) {
    const contentIdx = argv.indexOf('--content');
    const outputIdx = argv.indexOf('--output');
    return {
        contentDir: contentIdx !== -1 ? argv[contentIdx + 1] : './content',
        outputDir: outputIdx !== -1 ? argv[outputIdx + 1] : './dist',
    };
}
const args = process.argv.slice(2);
const command = args[0];
if (command === 'build') {
    const options = parseArgs(args);
    try {
        (0, build_1.build)(options);
        console.log(`Site built successfully in ${options.outputDir}`);
    }
    catch (err) {
        console.error('Error building site:', err.message);
        process.exit(1);
    }
}
else {
    console.log('Usage: npx ssg build [--content <dir>] [--output <dir>]');
    process.exit(0);
}
//# sourceMappingURL=index.js.map