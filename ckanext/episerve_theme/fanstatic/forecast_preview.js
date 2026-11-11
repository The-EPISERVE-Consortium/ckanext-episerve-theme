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

  /** Parse only explicit calendar dates and ISO weeks, preserving their meaning. */
  function calendar(value) {
    var text = String(value), week = /^(\d{4})-W(\d{2})$/.exec(text);
    if (week) {
      var number = Number(week[2]);
      if (number < 1 || number > 53) return null;
      var january = new Date(Date.UTC(Number(week[1]), 0, 4));
      return january.getTime() - ((january.getUTCDay() + 6) % 7) * 86400000 + (number - 1) * 604800000;
    }
    if (!/^\d{4}-\d{2}-\d{2}(?:[T ].*)?$/.test(text)) return null;
    var normalized = text.replace(' ', 'T');
    if (normalized.length > 10 && !/(Z|[+-]\d{2}:?\d{2})$/.test(normalized)) normalized += 'Z';
    var timestamp = Date.parse(normalized);
    return Number.isFinite(timestamp) ? timestamp : null;
  }

  /** Align one supplied series with its predictions without inferring model usage. */
  function combine(input, forecast) {
    var inputs = input ? input.points : [], outputs = forecast ? forecast.points : [];
    var allDates = inputs.concat(outputs).every(function (point) { return calendar(point.x) !== null; });
    var positional = input && forecast && forecast.position_axis && input.row_positions;
    var allNumeric = inputs.concat(outputs).every(function (point) { return point.x !== '' && Number.isFinite(Number(point.x)); });
    var sameAxis = !input || !forecast || input.axis === forecast.axis;
    var sharedCategories = input && forecast && inputs.some(function (point) {
      return outputs.some(function (other) { return point.x === other.x; });
    });
    var unaligned = Boolean(input && forecast && !allDates && !positional && !(allNumeric && sameAxis) && !(sameAxis && sharedCategories));
    var byKey = new Map(), sequence = 0;

    /** Add one source's observations to a shared coordinate map. */
    function add(points, history) {
      points.forEach(function (point, index) {
        var metric = allDates ? calendar(point.x) : (positional ? (history ? input.row_positions[index] : Number(point.x)) : (allNumeric ? Number(point.x) : null));
        var key = metric === null ? String(point.x) : String(metric);
        var merged = byKey.get(key);
        if (!merged) {
          merged = {x: allDates ? new Date(metric).toISOString().replace(/T00:00:00\.000Z$/, '') : (positional ? String(metric) : String(point.x)),
                    axis_value: metric === null ? sequence++ : metric};
          byKey.set(key, merged);
        }
        if (history) { merged.history = point.value; merged.input_x = point.x; }
        else { merged.value = point.value; merged.q10 = point.q10; merged.q90 = point.q90; }
      });
    }
    add(inputs, true); add(outputs, false);
    var points = Array.from(byKey.values()).sort(function (a, b) { return a.axis_value - b.axis_value; });
    var first = points.findIndex(function (point) { return Object.prototype.hasOwnProperty.call(point, 'value'); });
    var last = points.length - 1;
    while (last > first && !Object.prototype.hasOwnProperty.call(points[last], 'value')) last--;
    var viewStart = Math.max(0, first - Math.max(20, outputs.length * 4));
    var viewEnd = Math.max(viewStart + 2, last + 1);
    return {column: forecast ? forecast.column : input.column, label: forecast ? forecast.label : input.label,
            axis: allDates ? 'Date' : (positional ? 'Input row position' : (forecast ? forecast.axis : input.axis)),
            points: points, input_rows: input ? input.rows : 0, forecast_rows: forecast ? forecast.rows : 0,
            sampled: Boolean(input && input.sampled || forecast && forecast.sampled),
            duplicate_x: Boolean(input && input.duplicate_x || forecast && forecast.duplicate_x), unaligned: unaligned,
            initial_zoom: Math.min(100, Math.max(1, Math.ceil((viewEnd - viewStart) / Math.max(1, points.length) * 100))),
            initial_position: Math.round(viewStart / Math.max(1, points.length - (viewEnd - viewStart)) * 100)};
  }

  /** Offer compatible input and prediction series together in one chart. */
  function combinedChart(parent, result) {
    var choices = [];
    result.inputs.forEach(function (input) {
      input.series.forEach(function (series) { choices.push({series:series, filename:input.filename}); });
    });
    var controls = el('div', null, parent, 'epi-forecast-controls');
    var forecastLabel = el('label', 'Prediction series', controls, 'epi-forecast-series');
    var forecasts = el('select', null, forecastLabel);
    forecasts.setAttribute('aria-label', 'Prediction series');
    result.predictions.forEach(function (series, index) { var option = el('option', series.label, forecasts); option.value = index; });
    var inputLabel = el('label', 'Input supplied series', controls, 'epi-forecast-series');
    var inputSelect = el('select', null, inputLabel);
    inputSelect.setAttribute('aria-label', 'Input supplied series');
    var host = el('div', null, parent), selectedInputs = [];

    /** Replace the graph after a series choice while releasing old observers. */
    function render() {
      state.observers.forEach(function (observer) { observer.disconnect(); }); state.observers = [];
      host.replaceChildren();
      var input = selectedInputs[Number(inputSelect.value)];
      var forecast = result.predictions[Number(forecasts.value)];
      var merged = input || forecast ? [combine(input && input.series, forecast)] : [];
      chart(host, 'Input supplied & recorded predictions', merged, null, true);
    }

    /** Match target columns and retain explicit categorical input choices. */
    function chooseInputs() {
      var forecast = result.predictions[Number(forecasts.value)];
      selectedInputs = choices.filter(function (choice) { return !forecast || choice.series.column === forecast.column; });
      inputSelect.replaceChildren();
      selectedInputs.forEach(function (choice, index) {
        var option = el('option', choice.series.label + ' · ' + choice.filename, inputSelect); option.value = index;
      });
      if (!selectedInputs.length) { var option = el('option', 'No matching supplied input series', inputSelect); option.value = '-1'; }
      inputSelect.disabled = !selectedInputs.length;
      if (forecast) {
        var matching = selectedInputs.findIndex(function (choice) {
          return Object.keys(forecast.groups).every(function (key) { return choice.series.groups[key] === forecast.groups[key]; });
        });
        if (matching >= 0) inputSelect.value = matching;
      }
      render();
    }
    inputSelect.addEventListener('change', render);
    forecasts.addEventListener('change', chooseInputs);
    forecasts.disabled = !result.predictions.length;
    chooseInputs();
  }

  /** Render a selectable series with zoom, position controls, and pointer values. */
  function chart(parent, title, allSeries, table, forecast, preferredColumn) {
    var panel = el('section', null, parent, 'epi-forecast-panel');
    el('h3', title, panel);
    el('p', 'Black: input supplied · Red: recorded predictions · Shading: reported q10–q90', panel, 'epi-forecast-legend');
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
    if (allSeries.length === 1) label.style.display = 'none';
    var preferred = allSeries.findIndex(function (series) { return series.column === preferredColumn; });
    if (preferred >= 0) select.value = preferred;
    var zoomLabel = el('label', 'Visible range', controls), zoom = el('input', null, zoomLabel);
    zoom.type = 'range'; zoom.min = '1'; zoom.max = '100'; zoom.value = String(allSeries[0].initial_zoom || 100);
    zoom.setAttribute('aria-label', title + ' visible range');
    var positionLabel = el('label', 'Position', controls), position = el('input', null, positionLabel);
    position.type = 'range'; position.min = '0'; position.max = '100'; position.value = String(Math.min(100, allSeries[0].initial_position || 0));
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
      if (series.unaligned) {
        note.textContent = 'These recorded axes cannot be aligned reliably without guessing. Input and predictions remain available in the data tables below.';
        return;
      }
      if (series.duplicate_x) {
        note.textContent = 'Repeated axis values make a single line ambiguous. Use the series selector or data table.';
        return;
      }
      var count = Math.max(2, Math.ceil(original.length * Number(zoom.value) / 100));
      var start = Math.round(Math.max(0, original.length - count) * Number(position.value) / 100);
      var points = original.slice(start, start + count);
      note.textContent = series.axis + ' · ' + series.input_rows + ' supplied rows · ' + series.forecast_rows + ' predictions' +
        (series.sampled ? ' · input display is sampled; zoom changes the visible range' : '') +
        '. Input supplied does not imply every observation was used internally.';
      if (!points.length) { note.textContent = 'No values available.'; return; }
      var values = [];
      points.forEach(function (point) {
        ['history', 'value', 'q10', 'q90'].forEach(function (key) { if (Number.isFinite(point[key])) values.push(point[key]); });
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
      function x(index) {
        var first = points[0].axis_value, span = points[points.length - 1].axis_value - first;
        return left + (right - left) * (span ? (points[index].axis_value - first) / span : 0.5);
      }
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
        } else if (Object.prototype.hasOwnProperty.call(point, 'value')) flushBand();
      });
      flushBand();
      [['history', '#111827'], ['value', '#c62828']].forEach(function (line) {
        var path = '', connected = false;
        points.forEach(function (point, index) {
          if (!Object.prototype.hasOwnProperty.call(point, line[0])) return;
          var value = point[line[0]];
          if (!Number.isFinite(value)) { connected = false; return; }
          path += (connected ? 'L' : 'M') + x(index) + ',' + y(value) + ' '; connected = true;
          if (points.length <= 80 || line[0] === 'value') svgEl('circle', {cx:x(index), cy:y(value), r:2.5, fill:line[1]}, svg);
        });
        svgEl('path', {d:path, fill:'none', stroke:line[1], 'stroke-width':2, 'data-series':line[0]}, svg);
      });
      var boundary = points.findIndex(function (point) { return Object.prototype.hasOwnProperty.call(point, 'value'); });
      if (boundary >= 0) {
        svgEl('line', {x1:x(boundary), x2:x(boundary), y1:top, y2:bottom, stroke:'#64748b', 'stroke-dasharray':'4 4'}, svg);
      }
      if (forecast && points.some(function (point) { return Number.isFinite(point.q10) && Number.isFinite(point.q90); })) {
        svgEl('text', {x:left, y:height - 12, fill:'#52657d', 'font-size':11}, svg, 'Shading: reported q10–q90');
      }
      svg.addEventListener('pointermove', function (event) {
        var bounds = svg.getBoundingClientRect(), px = (event.clientX - bounds.left) * width / bounds.width;
        var index = 0, distance = Infinity;
        points.forEach(function (point, candidate) {
          var gap = Math.abs(x(candidate) - px); if (gap < distance) { index = candidate; distance = gap; }
        });
        var point = points[index];
        tooltip.textContent = point.x + ' · ' + series.column +
          (Object.prototype.hasOwnProperty.call(point, 'history') ? ' · input supplied: ' + (point.history === null ? 'missing' : point.history) : '') +
          (point.input_x && point.input_x !== point.x ? ' (' + point.input_x + ')' : '') +
          (Object.prototype.hasOwnProperty.call(point, 'value') ? ' · prediction: ' + (point.value === null ? 'missing' : point.value) : '') +
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
      combinedChart(content, result);
      result.inputs.forEach(function (input) {
        if (input.catalog) {
          var link = el('a', 'Source dataset at the recorded version ↗', content, 'epi-forecast-source');
          link.href = input.catalog; link.target = '_blank'; link.rel = 'noopener';
        }
        el('h4', 'Input supplied · ' + input.filename, content);
        tablePreview(content, input.table);
        if (input.sql && input.sql.trim()) {
          var sql = el('details', null, content);
          el('summary', 'Recorded workflow SQL', sql); el('pre', input.sql, sql);
        }
      });
      el('h4', 'Recorded predictions', content);
      tablePreview(content, result.prediction_table);
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
