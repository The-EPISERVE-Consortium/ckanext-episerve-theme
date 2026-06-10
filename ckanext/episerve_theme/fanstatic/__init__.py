import fanstatic

episerve_theme = fanstatic.Library("episerve_theme", ".")
episerve_css = fanstatic.Resource(
    episerve_theme,
    "episerve.css",
    depends=[],
)
