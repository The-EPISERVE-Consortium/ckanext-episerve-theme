import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from flask import Blueprint, Response
import urllib.request


def metabase_proxy(card_id):
    url = f"http://metabase.episerve.zib.de/api/public/card/{card_id}/query/json?"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
        return Response(data, content_type="application/json")
    except Exception:
        return Response("[]", status=502, content_type="application/json")


class EPIServeThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)

    def update_config(self, config):
        toolkit.add_template_directory(config, "templates")
        toolkit.add_resource("fanstatic", "episerve_theme")

    def get_blueprint(self):
        bp = Blueprint("episerve_theme", __name__)
        bp.add_url_rule(
            "/metabase-proxy/<card_id>",
            view_func=metabase_proxy,
        )
        return bp
