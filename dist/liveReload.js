"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.liveReloadScript = liveReloadScript;
exports.injectLiveReload = injectLiveReload;
function liveReloadScript() {
    return [
        '<script data-ssg-live-reload>',
        '(function(){',
        '  var ws=new WebSocket("ws://"+location.host);',
        '  ws.onmessage=function(e){ if(e.data==="reload"){ location.reload(); } };',
        '})();',
        '</script>',
    ].join('\n');
}
function injectLiveReload(html) {
    const script = liveReloadScript();
    if (/<\/body>/i.test(html)) {
        return html.replace(/<\/body>/i, `${script}\n</body>`);
    }
    return `${html}\n${script}\n`;
}
//# sourceMappingURL=liveReload.js.map