  // Row expand/collapse for the full-analysis detail row.
  // The fixture row is a real table row, so for keyboard access it also gets
  // role=button + tabindex=0 (set in _scan_table) and responds to
  // Enter/Space the same as a click.
  function toggleScanRow(id){
    var row = document.getElementById(id);
    var trigger = row ? row.previousElementSibling : null;
    if (row) row.classList.toggle('open');
    if (trigger) trigger.classList.toggle('open');
    updateScanRowA11y(row, trigger);
  }
  function updateScanRowA11y(row, trigger) {
    if (!row || !trigger) return;
    var open = row.classList.contains('open');
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    var region = row.querySelector('.full-analysis');
    if (region) region.setAttribute('aria-hidden', open ? 'false' : 'true');
  }
  // Enter/Space on a fixture row toggles it — mirror the onclick behaviour
  // without relying on event bubbling from a keypress on the cell.
  function onScanRowKey(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    var id = e.currentTarget.getAttribute('data-target');
    if (id) toggleScanRow(id);
  }
  // THE CALL cards — same expand/collapse pattern as scan rows, with
  // aria-expanded kept in sync (keyboard + click share one code path).
  function toggleCallCard(card) {
    card.classList.toggle('open');
    var open = card.classList.contains('open');
    card.setAttribute('aria-expanded', open ? 'true' : 'false');
    var region = card.querySelector('.full-analysis');
    if (region) region.setAttribute('aria-hidden', open ? 'false' : 'true');
  }
  function onCallCardKey(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    toggleCallCard(e.currentTarget);
  }
  // League group collapse is wired inline on each header row
  // (onclick toggles 'collapsed' on the parent tbody). Keyboard support +
  // aria-expanded on the header cell.
  function onLeagueGroupKey(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    var tbody = e.currentTarget.parentElement;
    if (!tbody) return;
    tbody.classList.toggle('collapsed');
    updateLeagueGroupA11y(tbody);
  }
  function updateLeagueGroupA11y(tbody) {
    var header = tbody.querySelector('.league-group-header');
    var btn = tbody.querySelector('.league-group-toggle');
    if (!header) return;
    var open = !tbody.classList.contains('collapsed');
    header.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (btn) btn.setAttribute('aria-hidden', open ? 'false' : 'true');
  }
