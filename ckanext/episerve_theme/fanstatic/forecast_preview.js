/* Generic input/output previews with a lazy, pinned ApexCharts renderer. */
(function () {
  'use strict';
  var state = {loading: false, loaded: false, charts: [], apexPromise: null};

  /** Create an element using textContent so artifact values remain inert text. */
  function el(tag, text, parent, cls) {
    var node = document.createElement(tag);
    if (text !== null && text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    if (parent) parent.appendChild(node);
    return node;
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

  /** Align supplied input, predictions, and explicitly associated observations.
   *
   * Args:
   *   input: Selected supplied-input series, or null.
   *   forecast: Selected recorded-prediction series, or null.
   *   reference: Matching benchmark observation series, or null.
   *
   * Returns:
   *   Combined chart points; observed values appear only at prediction coordinates.
   */
  function combine(input, forecast, reference) {
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
    // Only overlay observed values at existing prediction coordinates. Never
    // guess row positions or extend the model's supplied history with truth.
    if (reference && !reference.duplicate_x && !unaligned) {
      reference.points.forEach(function (point) {
        var metric = allDates ? calendar(point.x) : (!positional && sameAxis && reference.axis === (forecast || input).axis && allNumeric ? Number(point.x) : null);
        if ((allDates && metric === null) || positional) return;
        if (!allDates && reference.axis !== (forecast || input).axis) return;
        var key = metric === null ? String(point.x) : String(metric);
        var recorded = byKey.get(key);
        if (recorded && Object.prototype.hasOwnProperty.call(recorded, 'value')) recorded.observed = point.value;
      });
    }
    var points = Array.from(byKey.values()).sort(function (a, b) { return a.axis_value - b.axis_value; });
    var first = points.findIndex(function (point) { return Object.prototype.hasOwnProperty.call(point, 'value'); });
    var last = points.length - 1;
    while (last > first && !Object.prototype.hasOwnProperty.call(points[last], 'value')) last--;
    var viewStart = Math.max(0, first - Math.max(20, outputs.length * 4));
    var viewEnd = Math.max(viewStart + 2, last + 1);
    return {column: forecast ? forecast.column : input.column, label: forecast ? forecast.label : input.label,
            date_axis: allDates, axis: allDates ? 'Date' : (positional ? 'Input row position' : (forecast ? forecast.axis : input.axis)),
            points: points, observed_rows: points.filter(function (point) { return Object.prototype.hasOwnProperty.call(point, 'observed'); }).length,
            input_rows: input ? input.rows : 0, forecast_rows: forecast ? forecast.rows : 0,
            sampled: Boolean(input && input.sampled || forecast && forecast.sampled),
            duplicate_x: Boolean(input && input.duplicate_x || forecast && forecast.duplicate_x), unaligned: unaligned,
            initial_zoom: Math.min(100, Math.max(1, Math.ceil((viewEnd - viewStart) / Math.max(1, points.length) * 100))),
            initial_position: Math.round(viewStart / Math.max(1, points.length - (viewEnd - viewStart)) * 100)};
  }

  /** Locate a visual connector only when the supplied series ends before the forecast. */
  function forecastTransition(points) {
    var first = points.findIndex(function (point) { return Object.prototype.hasOwnProperty.call(point, 'value'); });
    var last = -1;
    points.forEach(function (point, index) { if (Object.prototype.hasOwnProperty.call(point, 'history')) last = index; });
    if (first < 0 || last < 0 || last >= first || !Number.isFinite(points[last].history) || !Number.isFinite(points[first].value)) return null;
    return {from:last, to:first};
  }

  /** Offer compatible input and prediction series together in one chart. */
  function combinedChart(parent, result) {
    var choices = [];
    result.inputs.forEach(function (input) {
      input.series.forEach(function (series) { choices.push({series:series, filename:input.filename, reference:input.reference}); });
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

    /** Replace the graph after a series choice while releasing library handlers. */
    async function render() {
      forecasts.disabled = true; inputSelect.disabled = true;
      destroyCharts();
      host.replaceChildren();
      var input = selectedInputs[Number(inputSelect.value)];
      var forecast = result.predictions[Number(forecasts.value)];
      var references = input && input.reference && forecast ? input.reference.series.filter(function (series) {
        return series.column === forecast.column && Object.keys(series.groups).every(function (key) {
          return series.groups[key] === forecast.groups[key] || series.groups[key] === input.series.groups[key];
        });
      }) : [];
      var merged = input || forecast ? [combine(input && input.series, forecast, references.length === 1 ? references[0] : null)] : [];
      try {
        await chart(host, 'Input supplied & recorded predictions', merged);
      } finally {
        forecasts.disabled = !result.predictions.length; inputSelect.disabled = !selectedInputs.length;
      }
    }

    /** Match target columns and retain explicit categorical input choices. */
    async function chooseInputs() {
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
      await render();
    }
    /** Keep chart update failures visible and retryable without uncaught promises. */
    function updateError(error) {
      el('p', 'The chart could not be updated. Change the selection to retry.', host, 'epi-forecast-note');
      console.error('Forecast chart update failed:', error);
    }
    inputSelect.addEventListener('change', function () { render().catch(updateError); });
    forecasts.addEventListener('change', function () { chooseInputs().catch(updateError); });
    forecasts.disabled = !result.predictions.length;
    return chooseInputs();
  }

  /** Load the pinned MIT-licensed chart library only after the tab is opened. */
  function loadApexCharts() {
    if (state.apexPromise) return state.apexPromise;
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/apexcharts@3.54.1/dist/apexcharts.min.js';
    script.integrity = 'sha384-KNaFJ+EK516RuHsoycvreec5pD7BkTKJEkjMrVSQWu9KGTl7En4dhIDv7t1DFJ+g';
    script.crossOrigin = 'anonymous';
    state.apexPromise = new Promise(function (resolve, reject) {
      var timer = setTimeout(function () { reject(new Error('The chart library could not be loaded. Please retry.')); }, 30000);
      script.onload = function () {
        clearTimeout(timer);
        if (typeof window.ApexCharts === 'function') resolve();
        else reject(new Error('The chart library is unavailable. Please retry.'));
      };
      script.onerror = function () { clearTimeout(timer); reject(new Error('The chart library could not be loaded. Please retry.')); };
      document.head.appendChild(script);
    }).catch(function (error) {
      script.remove(); state.apexPromise = null; throw error;
    });
    return state.apexPromise;
  }

  /** Release library event handlers and resize observers before replacing a chart. */
  function destroyCharts() {
    state.charts.forEach(function (instance) { instance.destroy(); });
    state.charts = [];
  }

  /** Compute the initial forecast-focused viewport without discarding earlier input. */
  function initialRange(series) {
    var points = series.points;
    var count = Math.max(2, Math.ceil(points.length * (series.initial_zoom || 100) / 100));
    var start = Math.round(Math.max(0, points.length - count) * Math.min(100, series.initial_position || 0) / 100);
    var selected = points.slice(start, start + count);
    return {min:selected[0].axis_value, max:selected[selected.length - 1].axis_value};
  }

  /** Build mixed range-area and line options from already aligned cached data. */
  function chartOptions(series) {
    var points = series.points, transition = forecastTransition(points);
    var fullMin = points[0].axis_value, fullMax = points[points.length - 1].axis_value;
    var range = initialRange(series);
    var dateAxis = series.date_axis;

    /** Format coordinates without converting recorded row positions into dates. */
    function formatX(value) {
      if (dateAxis) return new Date(Number(value)).toISOString().slice(0, 10);
      var match = points.find(function (point) { return point.axis_value === Number(value); });
      return match ? match.x : String(Number(Number(value).toPrecision(6)));
    }

    /** Preserve genuine nulls while omitting coordinates absent from this series. */
    function lineData(key) {
      return points.filter(function (point) { return Object.prototype.hasOwnProperty.call(point, key); }).map(function (point) {
        return {x:point.axis_value, y:Number.isFinite(point[key]) ? point[key] : null};
      });
    }
    var forecast = lineData('value');
    var band = points.filter(function (point) { return Object.prototype.hasOwnProperty.call(point, 'value'); }).map(function (point) {
      var valid = Number.isFinite(point.q10) && Number.isFinite(point.q90) && point.q10 <= point.q90;
      return {x:point.axis_value, y:valid ? [point.q10, point.q90] : [null, null]};
    });
    var hasBand = band.some(function (point) { return point.y.every(Number.isFinite); });
    if (!hasBand) band = [];
    var connector = transition ? [
      {x:points[transition.from].axis_value, y:points[transition.from].history},
      {x:points[transition.to].axis_value, y:points[transition.to].value}
    ] : [];
    return {
      chart: {
        type:hasBand ? 'rangeArea' : 'line', height:350, animations:{enabled:false}, fontFamily:'inherit',
        parentHeightOffset:0, redrawOnParentResize:true, redrawOnWindowResize:true,
        toolbar:{show:true, autoSelected:'zoom', tools:{download:true, selection:false, zoom:true, zoomin:true, zoomout:true, pan:true, reset:false,
          customIcons:[{icon:'<button type="button" class="epi-forecast-full-range">Full range</button>', title:'Show the full supplied range', index:0,
            click:function (chart) { return chart.updateOptions({xaxis:{min:fullMin, max:fullMax}}, false, false); }}]}},
        zoom:{enabled:true, type:'x', autoScaleYaxis:true}, events:{}
      },
      series: [
        {name:'Reported q10–q90', type:hasBand ? 'rangeArea' : 'line', data:band},
        {name:'Input supplied', type:'line', data:lineData('history')},
        {name:'Recorded predictions', type:'line', data:forecast},
        {name:'Transition', type:'line', data:connector},
        {name:'Observed values', type:'line', data:lineData('observed')}
      ],
      colors:['#c62828', '#111827', '#c62828', '#c62828', '#111827'],
      stroke:{curve:'straight', width:[0, 2, 2, 2, 2], dashArray:0},
      fill:{type:'solid', opacity:[0.16, 1, 1, 1, 1]},
      markers:{size:[0, 0, 3, 0, 2], strokeWidth:0, hover:{sizeOffset:2}},
      dataLabels:{enabled:false}, legend:{show:false},
      xaxis:{type:dateAxis ? 'datetime' : 'numeric', min:range.min, max:range.max,
             tickAmount:4, labels:{datetimeUTC:true, hideOverlappingLabels:true, formatter:formatX,
                                  style:{colors:'#52657d', fontSize:'11px'}}, tooltip:{enabled:false}},
      yaxis:{decimalsInFloat:3, labels:{style:{colors:'#52657d', fontSize:'11px'},
              formatter:function (value) { return Number.isFinite(value) ? Number(value.toPrecision(5)).toLocaleString() : ''; }}},
      grid:{borderColor:'#e2e8f0', padding:{left:8, right:12}},
      annotations:{xaxis:forecast.length ? [{x:forecast[0].x, borderColor:'#64748b', strokeDashArray:4}] : []},
      tooltip:{shared:false, intersect:false, enabledOnSeries:[0, 1, 2, 4],
        custom:function (context) {
          var entry = context.w.config.series[context.seriesIndex].data[context.dataPointIndex];
          if (!entry) return '';
          var point = points.find(function (candidate) { return candidate.axis_value === entry.x; });
          if (!point) return '';
          // Build text with DOM APIs, then serialize: version 3 expects an HTML string.
          var box = el('div', null, null, 'epi-forecast-apex-tooltip');
          el('strong', point.x, box);
          el('div', series.column, box);
          if (Object.prototype.hasOwnProperty.call(point, 'history')) {
            el('div', 'Input supplied: ' + (point.history === null ? 'missing' : point.history), box);
            if (point.input_x && point.input_x !== point.x) el('div', 'Input label: ' + point.input_x, box);
          }
          if (Object.prototype.hasOwnProperty.call(point, 'value')) el('div', 'Prediction: ' + (point.value === null ? 'missing' : point.value), box);
          if (Object.prototype.hasOwnProperty.call(point, 'observed')) el('div', 'Observed value: ' + (point.observed === null ? 'missing' : point.observed), box);
          if (Number.isFinite(point.q10) && Number.isFinite(point.q90)) el('div', 'Reported q10: ' + point.q10 + ' · q90: ' + point.q90, box);
          return box.outerHTML;
        }
      },
      responsive:[{breakpoint:600, options:{chart:{height:330}, xaxis:{tickAmount:2}, grid:{padding:{left:0, right:4}}}}]
    };
  }

  /** Render the combined chart using ApexCharts' native zoom, pan, reset and export. */
  async function chart(parent, title, allSeries) {
    var panel = el('section', null, parent, 'epi-forecast-panel');
    el('h3', title, panel);
    var legend = el('p', 'Black: input supplied · Red: recorded predictions · Shading: reported q10–q90', panel, 'epi-forecast-legend');
    var note = el('p', '', panel, 'epi-forecast-note');
    if (!allSeries.length) { note.textContent = 'A reliable chart mapping is unavailable. Inspect the recorded files in Resources.'; return; }
    var series = allSeries[0];
    if (series.observed_rows) legend.textContent += ' · Black: observed values';
    if (series.unaligned) {
      note.textContent = 'These recorded axes cannot be aligned reliably without guessing. Inspect the recorded input and predictions in Resources.'; return;
    }
    if (series.duplicate_x) { note.textContent = 'Repeated axis values make a single line ambiguous. Use the series selector or inspect the recorded files in Resources.'; return; }
    if (!series.points.length) { note.textContent = 'No values available.'; return; }
    note.textContent = series.axis + ' · ' + series.input_rows + ' supplied rows · ' + series.forecast_rows + ' predictions' + (series.observed_rows ? ' · ' + series.observed_rows + ' observed values' : '') +
      (series.sampled ? ' · input display is sampled' : '') + '. Input supplied does not imply every observation was used internally.';
    var host = el('div', null, panel, 'epi-forecast-chart');
    host.setAttribute('role', 'region'); host.setAttribute('aria-label', title + ': ' + series.label);
    el('p', 'Drag to zoom. Use the toolbar to pan, reset the full range, or download the chart.', panel, 'epi-forecast-note');
    // Omit chart.id: v3 copies its global named-chart registry into options,
    // creating cyclic configuration when a registered chart is later updated.
    var instance = new window.ApexCharts(host, chartOptions(series));
    state.charts.push(instance);
    try {
      await instance.render();
    } catch (error) {
      state.charts = state.charts.filter(function (candidate) { return candidate !== instance; });
      try { instance.destroy(); } catch (cleanupError) { /* Rendering never completed. */ }
      throw new Error('The interactive chart could not be rendered. Please retry.');
    }
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
      destroyCharts();
      content.replaceChildren();
      status.textContent = 'Run artifact version ' + result.artifact_commit.slice(0, 12) + ' · ' + (result.cached ? 'Saved preview' : 'Preview prepared');
      result.warnings.forEach(function (message) {
        el('p', message.replace('The recorded output is shown as a table.', 'Inspect the recorded output in Resources.'), content, 'epi-forecast-note');
      });
      result.inputs.forEach(function (input) {
        if (input.observation_note) el('p', input.observation_note, content, 'epi-forecast-note');
      });
      var chartError = null;
      try {
        await loadApexCharts();
        await combinedChart(content, result);
      } catch (error) {
        chartError = error;
        el('p', error.message + ' Recorded files remain available in Resources.', content, 'epi-forecast-note');
      }
      state.loaded = result.cacheable && !chartError;
      retry.hidden = state.loaded;
      if (chartError) status.textContent = chartError.message;
    } catch (error) {
      status.textContent = error.message || 'Preview unavailable. Please retry.';
      retry.hidden = false;
    } finally { state.loading = false; }
    retry.onclick = function () { window.epiForecast(); };
  };
  /** Prepare the preview on page load when Input & Forecast is the default tab. */
  function initializeForecast() {
    var pane = document.getElementById('tab-forecast');
    if (pane && pane.style.display !== 'none') window.epiForecast();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeForecast);
  else initializeForecast();
}());
