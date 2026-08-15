"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const cli_1 = require("./cli");
(0, cli_1.main)(process.argv.slice(2)).catch((err) => {
    if (err instanceof cli_1.HelpError) {
        process.stderr.write(`${err.message}\n`);
        process.exit(0);
    }
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`Error: ${message}\n`);
    process.exit(1);
});
