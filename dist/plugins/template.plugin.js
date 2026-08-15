"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const template_1 = require("../template");
exports.TemplatePlugin = {
    name: 'template',
    beforeBuild: async (context) => {
        if (context.templateDir) {
            await (0, template_1.loadPartials)(context.templateDir);
        }
    },
    onFile: async (page, context) => {
        if (!context.templateDir) {
            return page;
        }
        const eng = (0, template_1.getEngine)();
        let html = page.html;
        if (page.template) {
            const templateContent = await (0, template_1.loadTemplate)(page.template, context.templateDir);
            html = eng.render(templateContent, { ...page, body: page.html });
        }
        if (page.layout) {
            const layout = await (0, template_1.loadLayout)(page.layout, context.templateDir);
            html = eng.render(layout, { ...page, body: html });
        }
        return {
            ...page,
            html
        };
    }
};
//# sourceMappingURL=template.plugin.js.map