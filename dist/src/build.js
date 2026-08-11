"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const engine_1 = require("./engine");
function build(contentDir, outputDir, templatesDir, options) {
    const engine = new engine_1.SsgEngine();
    engine.build(contentDir, outputDir, templatesDir, options);
}
//# sourceMappingURL=build.js.map