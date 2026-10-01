import os
import urllib.request

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from flask import Blueprint, Response

from ckanext.episerve_theme import signing


def episerve_signed_url(url):
    """Template helper: sign a DOIP component URL for the current visitor.

    Only logged-in users get a signed link (valid for ``DOIP_LINK_TTL`` seconds,
    default one hour); anonymous visitors, non-DOIP URLs, and deployments without
    ``DOIP_LINK_SECRET`` get the URL unchanged. The DOIP server accepts the link for
    restricted datasets only, for exactly that component.
    """
    if not toolkit.current_user.is_authenticated:
        return url
    doip_public_url = os.environ.get("DOIP_PUBLIC_URL", "https://doip.episerve.zib.de").rstrip("/")
    return signing.sign_doip_url(
        url,
        retrieve_base=f"{doip_public_url}/doip/retrieve/",
        secret=os.environ.get("DOIP_LINK_SECRET", ""),
        ttl=int(os.environ.get("DOIP_LINK_TTL", "3600")),
    )


def metabase_proxy(card_id):
    url = f"http://metabase.default.svc.cluster.local/api/public/card/{card_id}/query/json?"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
        return Response(data, content_type="application/json")
    except Exception:
        return Response("[]", status=502, content_type="application/json")


class EPIServeThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.ITemplateHelpers)

    def get_helpers(self):
        return {"episerve_signed_url": episerve_signed_url}

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
