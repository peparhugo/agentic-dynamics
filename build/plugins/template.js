"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const generator_1 = require("../generator");
class TemplatePlugin {
    constructor() {
        this.name = 'template';
    }
    afterBuild(context) {
        const genStats = { built: 0, skipped: 0 };
        const hasCache = context.cache && context.cache.isPopulated();
        (0, generator_1.generateSite)(context.pages, context.options.output, context.options.templates, context.cache, genStats);
        if (context.stats && hasCache) {
            context.stats.pagesBuilt = genStats.built;
            context.stats.pagesSkipped = genStats.skipped;
        }
        else if (context.stats) {
            context.stats.pagesBuilt = genStats.built;
            context.stats.pagesSkipped = 0;
        }
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template.js.map