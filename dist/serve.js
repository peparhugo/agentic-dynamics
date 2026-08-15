import fs from 'fs';
import { generate } from './generator.js';
import { PluginManager } from './plugin.js';
import { DevServerPlugin } from './plugins/dev-server-plugin.js';
export async function serve(options, test) {
    const port = options.port || 3000;
    const { contentDir, outputDir } = options;
    const templatesDir = options.templatesDir || './templates';
    const layoutsDir = options.layoutsDir || './templates/layouts';
    const partialsDir = options.partialsDir || './templates/partials';
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    const rebuildSite = async () => {
        await generate({
            contentDir,
            outputDir,
            templatesDir,
            layoutsDir,
            partialsDir
        });
    };
    const devServerPlugin = new DevServerPlugin({
        port,
        onRebuild: rebuildSite,
        test
    });
    const pluginManager = new PluginManager();
    pluginManager.addPlugin(devServerPlugin);
    const context = {
        contentDir,
        outputDir,
        templatesDir,
        layoutsDir,
        partialsDir,
        pages: []
    };
    await pluginManager.callHook('onStart', context);
    return {
        close: async () => {
            await pluginManager.callHook('onEnd', context);
        }
    };
}
//# sourceMappingURL=serve.js.map