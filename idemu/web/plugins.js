'use strict';
/* IDEmu – extensões de host (pasta plugins/, docs/PLUGINS.md).
   Pede /api/plugins, injeta os .css/.js de cada pacote em ordem e oferece o ponto de entrada:
     IDE.registerTab({ id, label, icon, mount(host, ctx) })  → aba nova na tela Execução
   O script do plugin roda na página como qualquer outro: usa IDE.api/IDE.post e o que mais a GUI usa. */
(function (IDE) {
  IDE.pluginTabs = [];                        // [id, label, icon] – run.js mistura na barra da tela Execução

  IDE.registerTab = function (def) {
    if (!def || !/^[a-z0-9][a-z0-9_-]{0,31}$/.test(String(def.id || '')) || typeof def.mount !== 'function' || !IDE.tabDefs) return null;
    IDE.tabDefs[def.id] = { mount: def.mount };
    const entry = [def.id, def.label || def.id, def.icon || 'wrench'];
    const at = IDE.pluginTabs.findIndex((t) => t[0] === def.id);
    if (at >= 0) IDE.pluginTabs[at] = entry; else IDE.pluginTabs.push(entry);
    IDE.emit('plugins:tab', entry);           // a tela Execução já aberta ganha o botão na hora
    return entry;
  };

  function inject(url, tag, attr) {
    return new Promise((res) => {
      const el = document.createElement(tag);
      el.onload = el.onerror = () => res();   // um arquivo que falha não trava os demais
      el[attr] = url;
      document.head.appendChild(el);
    });
  }

  /** Relemos a lista (isto também é o que POST /api/plugins/rescan pede que o navegador faça). */
  IDE.pluginsLoad = async function () {
    let data;
    try { data = await IDE.api('/api/plugins'); } catch (e) { return null; }
    for (const p of data.plugins || []) {
      for (const css of p.styles || []) await inject('/plugins/' + encodeURIComponent(p.id) + '/' + css.split('/').map(encodeURIComponent).join('/'), 'link', 'href');
      for (const js of p.scripts || []) await inject('/plugins/' + encodeURIComponent(p.id) + '/' + js.split('/').map(encodeURIComponent).join('/'), 'script', 'src');
    }
    IDE.plugins = data;
    IDE.emit('plugins:loaded', data);
    return data;
  };
  IDE.pluginsLoad();
})(window.IDE);
