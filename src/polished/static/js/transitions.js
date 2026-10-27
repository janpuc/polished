// Row to detail: the shade tip travels from its row (or the Home rack) to the head of the shade page,
// a cross-document view transition (docs/VISUAL.md section 8; Safari 18.2 and Chrome, a plain
// navigation elsewhere). The tip of the row and the tip of the head share one name, `tip-{id}`, set
// only on that pair as the page is left and as the next one is revealed: a style attribute would
// break the CSP, and naming every row would make the names collide.
//
// A classic script, loaded in the head without defer: `pagereveal` fires before the first paint,
// which a deferred or module script can miss.
(function () {
  var SHADE_PATH = /^\/shades\/(\d+)$/;

  // A transition the browser skips (a second navigation, a hidden tab) rejects its promises;
  // nothing here waits on them, so the rejection is absorbed rather than logged.
  function settle(transition) {
    [transition.ready, transition.finished, transition.updateCallbackDone].forEach(function (promise) {
      promise.catch(function () {});
    });
  }

  window.addEventListener("pageswap", function (event) {
    if (!event.viewTransition) return;
    settle(event.viewTransition);
    if (!event.activation || !event.activation.entry) return;
    var match = SHADE_PATH.exec(new URL(event.activation.entry.url).pathname);
    if (!match) return;
    var tip = document.querySelector('a[href="/shades/' + match[1] + '"] .tip');
    if (tip) tip.style.setProperty("view-transition-name", "tip-" + match[1]);
  });

  window.addEventListener("pagereveal", function (event) {
    if (!event.viewTransition) return;
    settle(event.viewTransition);
    var match = SHADE_PATH.exec(location.pathname);
    var tip = match && document.querySelector(".detail-head .tip");
    if (tip) tip.style.setProperty("view-transition-name", "tip-" + match[1]);
  });
})();
