# Model-run forecast charts

The Input & Forecast tab uses **ApexCharts 3.54.1**, loaded from jsDelivr only
when the tab is shown and preview data are available. Input & Forecast is the
first and default tab for model runs, so their preview loads on page open. The script URL is pinned
and checked with SHA-384 subresource integrity. This release is MIT licensed:
https://github.com/apexcharts/apexcharts.js/blob/v3.54.1/LICENSE

The chart combines straight input and prediction lines with a range-area band for
reported q10/q90 values and a black line for available observed values. Lines
are solid; point markers have no white border. A solid transition joins the last supplied value
to the first prediction only when the input ends before the forecast. It does not
add observations or predictions. Backtests retain their overlapping series.

The existing date/ISO-week/row-position alignment, compact series selectors, API,
and database cache remain unchanged. The library handles zoom, panning, full-range
reset, image/data exports, tooltips and resizing. Display sampling still applies;
exports contain the plotted sample, not the complete original source file.

The forecast region is shown initially. Full range restores the full supplied
range. The tab ends with the chart: source/reference links, preview tables, SQL
and configuration details are omitted because sources, workflow SQL and run
artifacts are accessible elsewhere on the run page. Unavailable-data messages
remain visible. If the library is unavailable, the message points to Resources
and Retry preview can reload the chart. Changing series destroys the old chart to
release its listeners and resize observers.

When changing the library version, update both the pinned URL and integrity hash
in `forecast_preview.js`. Verify the chosen release's license rather than assuming
newer ApexCharts releases use the same terms. The homepage renderer is unchanged.
