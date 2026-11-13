"""Exercise generic browser axis alignment without a chart-library dependency."""

from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node is needed to exercise browser alignment functions')
def test_combined_chart_aligns_dates_weeks_positions_and_backtests():
    """Overlay matching observations while refusing unknown axis relationships."""
    source = Path(__file__).parents[1] / 'ckanext/episerve_theme/fanstatic/forecast_preview.js'
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8').replace('}());', 'window.combine = combine; window.forecastTransition = forecastTransition; window.chartOptions = chartOptions;}());');
const context = {window:{}, document:{readyState:'complete', getElementById:()=>null}};
vm.runInNewContext(source, context);
const combine = context.window.combine;
const transition = context.window.forecastTransition;
const options = context.window.chartOptions;
/** Construct generic chart series for axis tests. */
function series(axis, points, extras) {
  return Object.assign({axis, points, column:'value', label:'value', rows:points.length, groups:{}, duplicate_x:false}, extras || {});
}
let input = series('day', [{x:'2026-01-01',value:1},{x:'2026-01-02',value:2}]);
let output = series('day', [{x:'2026-01-02',value:3,q10:2,q90:4},{x:'2026-01-03',value:5,q10:4,q90:6}]);
let combined = combine(input, output);
assert.equal(combined.points.length, 3);
assert.equal(combined.points[1].history, 2);
assert.equal(combined.points[1].value, 3);
assert.equal(combined.points[1].q90, 4);
assert.equal(combined.unaligned, false);
assert.equal(transition(combined.points), null); // Backtest observations continue into the forecast.
let future = combine(series('day', [{x:'2026-01-01',value:1},{x:'2026-01-02',value:2}]),
                     series('day', [{x:'2026-01-03',value:3,q10:2,q90:4},{x:'2026-01-04',value:4,q10:3,q90:5}]));
assert.equal(transition(future.points).from, 1);
assert.equal(transition(future.points).to, 2);
const truth = series('day', [{x:'2026-01-02',value:99},{x:'2026-01-03',value:7},{x:'2026-01-04',value:null},{x:'2026-01-05',value:10}]);
let observed = combine(series('day', [{x:'2026-01-01',value:1},{x:'2026-01-02',value:2}]),
                       series('day', [{x:'2026-01-03',value:3},{x:'2026-01-04',value:4}]), truth);
assert.equal(observed.points.length, 4); // Do not extend the prediction range with truth.
assert.equal(observed.observed_rows, 2);
assert.equal(observed.points[1].observed, undefined); // Truth is never supplied input.
assert.equal(observed.points[2].observed, 7);
assert.equal(observed.points[2].history, undefined);
assert.equal(observed.points[3].observed, null);
assert.equal(options(observed).series[4].name, 'Observed values');
assert.equal(options(observed).series[4].data[0].y, 7);
assert.equal(options(observed).series[4].data[1].y, null);
assert.equal(options(observed).series[1].data.length, 2);
assert.equal(options(observed).series[3].data.length, 2);
assert.equal(combine(input, output, Object.assign({}, truth, {duplicate_x:true})).observed_rows, 0);
let configuration = options(future);
assert.equal(configuration.chart.type, 'rangeArea');
assert.equal(configuration.chart.id, undefined); // Avoid v3 named-chart registry cycles on updates.
assert.equal(configuration.xaxis.type, 'datetime');
assert.equal(configuration.stroke.curve, 'straight');
assert.equal(configuration.series[1].data.length, 2);
assert.equal(configuration.series[2].data.length, 2);
assert.equal(configuration.series[3].data.length, 2);
assert.equal(configuration.series[3].data[0].y, 2);
assert.equal(configuration.series[3].data[1].y, 3);
let reset;
configuration.chart.toolbar.tools.customIcons[0].click({updateOptions:(value)=>{reset=value;}});
assert.equal(reset.xaxis.min, future.points[0].axis_value);
assert.equal(reset.xaxis.max, future.points[3].axis_value);

assert.equal(future.points.length, 4); // Connector never inserts observations or predictions.
future.points[1].history = null;
assert.equal(options(future).series[1].data[1].y, null);
assert.equal(transition(future.points), null); // Preserve actual missing observations.
assert.equal(transition([{x:'1', value:3}]), null);
input = series('week', [{x:'2026-W01',value:1}]);
output = series('date', [{x:'2025-12-29',value:2}]);
combined = combine(input, output);
assert.equal(combined.points.length, 1);
assert.equal(combined.points[0].x, '2025-12-29');
assert.equal(combined.points[0].history, 1);
assert.equal(combined.points[0].value, 2);
input = series('day', [{x:'2026-01-01',value:10},{x:'2026-01-02',value:20},{x:'2026-01-03',value:30}], {row_positions:[101,102,103]});
output = series('day', [{x:'102',value:21},{x:'103',value:31},{x:'104',value:41}], {position_axis:true});
combined = combine(input, output);
assert.equal(combined.axis, 'Input row position');
assert.equal(options(combined).xaxis.type, 'numeric');
assert.equal(options(combined).series[3].data.length, 0);
assert.equal(options(combined).chart.type, 'line');
assert.equal(options(combined).series[0].data.length, 0);
assert.equal(combined.points.length, 4);
assert.equal(combined.points[1].history, 20);
assert.equal(combined.points[1].value, 21);
assert.equal(combined.points[1].input_x, '2026-01-02');
assert.equal(combined.points[3].x, '104');
assert.equal(combined.unaligned, false);
output.position_axis = false;
assert.equal(combine(input, output).unaligned, true);
combined = combine(null, output);
assert.equal(combined.input_rows, 0);
assert.equal(combined.forecast_rows, 3);
assert.equal(combined.unaligned, false);
'''
    subprocess.run(['node', '-e', script, str(source)], check=True, capture_output=True, text=True)
