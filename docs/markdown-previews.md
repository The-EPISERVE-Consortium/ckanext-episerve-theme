# Raw text previews

The sync registers `MD`, `MARKDOWN`, `TXT`, `XML`, `CONF`, `YAML` and `YML` resources with CKAN's existing `text_view`.
The renderer treats content as plain text, retaining Markdown syntax and escaping
embedded HTML. It does not load Markdown libraries or render headings and links.

The theme's `text_view.html` override uses `episerve_file_url` for these formats. This
keeps the page's pinned lakeFS version and uses the existing signed-link handling
for logged-in visitors to restricted DOIP files. XML rendering is forced to the plain-text path, without parsing or highlighting.
Other text view formats retain
their current behavior.

Existing resources need a one-time view backfill after deployment; the sync repo
provides `python -m maintenance.backfill_text_previews --apply`. Its default
mode is a dry run, and it skips resources that already have a text view.
