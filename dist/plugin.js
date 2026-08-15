"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isPlugin = isPlugin;
function isPlugin(value) {
    if (!value || typeof value !== 'object') {
        return false;
    }
    const candidate = value;
    return (typeof candidate.name === 'string' &&
        (typeof candidate.onStart === 'function' ||
            typeof candidate.beforeBuild === 'function' ||
            typeof candidate.onFile === 'function' ||
            typeof candidate.afterBuild === 'function' ||
            typeof candidate.onEnd === 'function'));
}
//# sourceMappingURL=plugin.js.map