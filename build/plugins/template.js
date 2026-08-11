"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const generator_1 = require("../generator");
class TemplatePlugin {
    constructor() {
        this.name = 'template';
    }
    afterBuild(context) {
        (0, generator_1.generateSite)(context.pages, context.options.output, context.options.templates);
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template.js.map