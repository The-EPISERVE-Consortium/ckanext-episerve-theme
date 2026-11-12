# Model-run forecast charts

The Input & Forecast tab uses **ApexCharts 3.54.1**, loaded from jsDelivr only
when the tab is opened and preview data are available. The script URL is pinned
and checked with SHA-384 subresource integrity. This release is MIT licensed:
https://github.com/apexcharts/apexcharts.js/blob/v3.54.1/LICENSE

The chart combines straight input and prediction lines with a range-area band for
reported q10/q90 values. A separate dashed line connects the last supplied value
to the first prediction only when the input ends before the forecast. It does not
add observations or predictions. Backtests retain their overlapping series.

The existing date/ISO-week/row-position alignment, compact series selectors, API,
and database cache remain unchanged. The library handles zoom, panning, full-range
reset, image/data exports, tooltips and resizing. Display sampling still applies;
exports contain the plotted sample, not the complete original source file.

The forecast region is shown initially. Full range restores the full supplied
range. If the library is unavailable, the data tables remain readable and the
Retry preview button can reload it. Changing series destroys the old chart to
release its listeners and resize observers.

When changing the library version, update both the pinned URL and integrity hash
in `forecast_preview.js`. Verify the chosen release's license rather than assuming
newer ApexCharts releases use the same terms. The homepage renderer is unchanged.
