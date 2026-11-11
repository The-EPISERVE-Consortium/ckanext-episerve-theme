/* Generic input/output charts. No model-specific rules or external chart scripts. */
(function () {
  'use strict';
  var state = {loading: false, loaded: false, observers: []};

  /** Create an element using textContent so artifact values remain inert text. */
  function el(tag, text, parent, cls) {
    var node = document.createElement(tag);
    if (text !== null && text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    if (parent) parent.appendChild(node);
    return node;
  }

  /** Create a native SVG element with fixed attribute names. */
  function svgEl(tag, attrs, parent, text) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text !== undefined) node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  /** Add a bounded table retaining recorded values for inspection and fallback. */
  function tablePreview(parent, table) {
    if (!table) return;
    var details = el('details', null, parent);
    el('summary', 'Data table · first ' + table.rows.length + ' of ' + table.total + ' rows', details);
    var wrap = el('div', null, details, 'epi-forecast-table');
    var tableEl = el('table', null, wrap), tr = el('tr', null, el('thead', null, tableEl));
    table.columns.forEach(function (column) { var th = el('th', column, tr); th.scope = 'col'; });
    var body = el('tbody', null, tableEl);
    table.rows.forEach(function (row) {
      var line = el('tr', null, body);
      row.forEach(function (cell) { el('td', cell, line); });
    });
  }

  /** Render a selectable series with zoom, position controls, and pointer values. */
  function chart(parent, title, allSeries, table, forecast, preferredColumn) {
    var panel = el('section', null, parent, 'epi-forecast-panel');
    el('h3', title, panel);
    if (!allSeries.length) {
      el('p', 'A reliable chart mapping is unavailable. Inspect the recorded data below.', panel, 'epi-forecast-note');
      tablePreview(panel, table);
      return;
    }
    var controls = el('div', null, panel, 'epi-forecast-controls');
    var label = el('label', 'Series', controls, 'epi-forecast-series');
    var select = el('select', null, label);
    select.setAttribute('aria-label', title + ' series');
    allSeries.forEach(function (series, index) { var option = el('option', series.label, select); option.value = index; });
    var preferred = allSeries.findIndex(function (series) { return series.column === preferredColumn; });
    if (preferred >= 0) select.value = preferred;
    var zoomLabel = el('label', 'Visible range', controls), zoom = el('input', null, zoomLabel);
    zoom.type = 'range'; zoom.min = '5'; zoom.max = '100'; zoom.value = '100';
    zoom.setAttribute('aria-label', title + ' visible range');
    var positionLabel = el('label', 'Position', controls), position = el('input', null, positionLabel);
    position.type = 'range'; position.min = '0'; position.max = '100'; position.value = '100';
    position.setAttribute('aria-label', title + ' position');
    var note = el('p', '', panel, 'epi-forecast-note');
    var host = el('div', null, panel, 'epi-forecast-chart');
    var tooltip = el('p', 'Move over the graph for exact displayed values.', panel, 'epi-forecast-tooltip');
    tablePreview(panel, table);

    /** Draw recorded observations in their original order without inferring dates. */
    function draw() {
      host.replaceChildren();
      var series = allSeries[Number(select.value)], original = series.points;
      position.disabled = zoom.value === '100';
      if (series.duplicate_x) {
        note.textContent = 'Repeated axis values make a single line ambiguous. Use the series selector or data table.';
        return;
      }
      var count = Math.max(2, Math.ceil(original.length * Number(zoom.value) / 100));
      var start = Math.round(Math.max(0, original.length - count) * Number(position.value) / 100);
      var points = original.slice(start, start + count);
      note.textContent = series.axis + ' · ' + series.rows + ' recorded rows' +
        (series.sampled ? ' · evenly spaced display sample of ' + original.length + ' points' : '') +
        '. Rows retain their recorded order; input and forecast axes are shown separately.';
      if (!points.length) { note.textContent = 'No values available.'; return; }
      var values = [];
      points.forEach(function (point) {
        ['value', 'q10', 'q90'].forEach(function (key) { if (Number.isFinite(point[key])) values.push(point[key]); });
      });
      if (!values.length) { note.textContent += ' No finite values are available.'; return; }
      var width = Math.max(280, host.clientWidth), height = 280;
      var left = 65, right = width - 18, top = 18, bottom = 225;
      var low = Math.min.apply(null, values), high = Math.max.apply(null, values);
      var padding = (high - low) * 0.08 || Math.max(Math.abs(high) * 0.05, 1);
      low -= padding; high += padding;
      var svg = svgEl('svg', {viewBox: '0 0 ' + width + ' ' + height, role: 'img', 'aria-label': title + ': ' + series.label}, host);
      svgEl('title', {}, svg, title + ': ' + series.label);

      /** Map a recorded row index to a plot coordinate. */
      function x(index) { return left + (right - left) * index / Math.max(1, points.length - 1); }
      /** Map a finite numeric value to a plot coordinate. */
      function y(value) { return bottom - (bottom - top) * (value - low) / (high - low); }
      for (var tick = 0; tick <= 4; tick++) {
        var value = low + (high - low) * tick / 4, py = y(value);
        svgEl('line', {x1:left, x2:right, y1:py, y2:py, stroke:'#e2e8f0'}, svg);
        svgEl('text', {x:left - 8, y:py + 4, 'text-anchor':'end', fill:'#52657d', 'font-size':11}, svg, Number(value.toPrecision(4)).toLocaleString());
      }
      (width < 550 ? [0, points.length - 1] : [0, Math.floor((points.length - 1) / 2), points.length - 1]).filter(function (v, i, a) { return a.indexOf(v) === i; }).forEach(function (index, i, ticks) {
        svgEl('text', {x:x(index), y:bottom + 22, 'text-anchor':i === 0 ? 'start' : (i === ticks.length - 1 ? 'end' : 'middle'), fill:'#52657d', 'font-size':11}, svg, points[index].x);
      });
      var band = [];
      /** Flush one continuous segment of valid reported quantiles. */
      function flushBand() {
        if (band.length > 1) {
          var coords = band.map(function (p) { return x(p.index) + ',' + y(p.q90); }).concat(
            band.slice().reverse().map(function (p) { return x(p.index) + ',' + y(p.q10); }));
          svgEl('polygon', {points:coords.join(' '), fill:'rgba(198,40,40,0.16)'}, svg);
        }
        band = [];
      }
      points.forEach(function (point, index) {
        if (Number.isFinite(point.q10) && Number.isFinite(point.q90) && point.q10 <= point.q90) {
          band.push({index:index, q10:point.q10, q90:point.q90});
        } else flushBand();
      });
      flushBand();
      var path = '', connected = false;
      points.forEach(function (point, index) {
        if (!Number.isFinite(point.value)) { connected = false; return; }
        path += (connected ? 'L' : 'M') + x(index) + ',' + y(point.value) + ' ';
        connected = true;
        if (points.length <= 60) svgEl('circle', {cx:x(index), cy:y(point.value), r:2.5, fill:forecast ? '#c62828' : '#111827'}, svg);
      });
      svgEl('path', {d:path, fill:'none', stroke:forecast ? '#c62828' : '#111827', 'stroke-width':2}, svg);
      if (forecast && points.some(function (point) { return Number.isFinite(point.q10) && Number.isFinite(point.q90); })) {
        svgEl('text', {x:left, y:height - 12, fill:'#52657d', 'font-size':11}, svg, 'Shading: reported q10–q90');
      }
      svg.addEventListener('pointermove', function (event) {
        var bounds = svg.getBoundingClientRect(), px = (event.clientX - bounds.left) * width / bounds.width;
        var index = Math.max(0, Math.min(points.length - 1, Math.round((px - left) / (right - left) * (points.length - 1))));
        var point = points[index];
        tooltip.textContent = point.x + ' · ' + series.column + ': ' + (point.value === null ? 'missing' : point.value) +
          (forecast && Number.isFinite(point.q10) && Number.isFinite(point.q90) ? ' · reported q10: ' + point.q10 + ', q90: ' + point.q90 : '');
      });
    }
    select.addEventListener('change', draw);
    zoom.addEventListener('input', draw);
    position.addEventListener('input', draw);
    if (window.ResizeObserver) {
      var observer = new ResizeObserver(draw);
      observer.observe(host); state.observers.push(observer);
    }
    draw();
  }

  /** Fetch preview JSON only when the model-run tab is opened, allowing retries. */
  window.epiForecast = async function () {
    var root = document.querySelector('.epi-forecast');
    if (!root || state.loading || state.loaded) return;
    var status = root.querySelector('.epi-forecast-status'), retry = root.querySelector('.epi-forecast-retry');
    var content = root.querySelector('.epi-forecast-content');
    state.loading = true; retry.hidden = true;
    status.textContent = 'Preparing input and forecast preview…';
    try {
      var url = '/forecast-preview/' + encodeURIComponent(root.dataset.qid);
      if (root.dataset.version) url += '?version=' + encodeURIComponent(root.dataset.version);
      var response = await fetch(url, {credentials:'same-origin', cache:'no-store'});
      var result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Preview unavailable.');
      state.observers.forEach(function (observer) { observer.disconnect(); });
      state.observers = [];
      content.replaceChildren();
      status.textContent = 'Run artifact version ' + result.artifact_commit.slice(0, 12) + ' · ' + (result.cached ? 'Saved preview' : 'Preview prepared');
      result.warnings.forEach(function (message) { el('p', message, content, 'epi-forecast-note'); });
      result.inputs.forEach(function (input) {
        if (input.catalog) {
          var link = el('a', 'Source dataset at the recorded version ↗', content, 'epi-forecast-source');
          link.href = input.catalog; link.target = '_blank'; link.rel = 'noopener';
        }
        chart(content, 'Input supplied · ' + input.filename, input.series, input.table, false, result.predictions.length ? result.predictions[0].column : null);
        if (input.sql && input.sql.trim()) {
          var sql = el('details', null, content);
          el('summary', 'Recorded workflow SQL', sql); el('pre', input.sql, sql);
        }
      });
      chart(content, 'Recorded predictions', result.predictions, result.prediction_table, true);
      var config = el('details', null, content);
      el('summary', 'Run configuration', config); el('pre', JSON.stringify(result.config, null, 2), config);
      state.loaded = result.cacheable;
      retry.hidden = result.cacheable;
    } catch (error) {
      status.textContent = error.message || 'Preview unavailable. Please retry.';
      retry.hidden = false;
    } finally { state.loading = false; }
    retry.onclick = function () { window.epiForecast(); };
  };
}());
