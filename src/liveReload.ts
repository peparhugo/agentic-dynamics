export function liveReloadScript(): string {
  return [
    '<script data-ssg-live-reload>',
    '(function(){',
    '  var ws=new WebSocket("ws://"+location.host);',
    '  ws.onmessage=function(e){ if(e.data==="reload"){ location.reload(); } };',
    '})();',
    '</script>',
  ].join('\n');
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  return `${html}\n${script}\n`;
}
