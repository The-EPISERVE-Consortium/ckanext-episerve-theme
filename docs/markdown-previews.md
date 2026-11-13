# Raw Markdown previews

The sync registers `MD` and `MARKDOWN` resources with CKAN's existing `text_view`.
The renderer treats content as plain text, retaining Markdown syntax and escaping
embedded HTML. It does not load Markdown libraries or render headings and links.

The theme's `text_view.html` override uses `episerve_file_url` for Markdown. This
keeps the page's pinned lakeFS version and uses the existing signed-link handling
for logged-in visitors to restricted DOIP files. Other text view formats retain
their current behavior.

Existing resources need a one-time view backfill after deployment; the sync repo
provides `python -m maintenance.backfill_markdown_previews --apply`. Its default
mode is a dry run, and it skips resources that already have a text view.
