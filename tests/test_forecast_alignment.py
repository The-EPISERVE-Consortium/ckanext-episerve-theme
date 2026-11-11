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
const source = fs.readFileSync(process.argv[1], 'utf8').replace('}());', 'window.combine = combine;}());');
const context = {window:{}};
vm.runInNewContext(source, context);
const combine = context.window.combine;
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
