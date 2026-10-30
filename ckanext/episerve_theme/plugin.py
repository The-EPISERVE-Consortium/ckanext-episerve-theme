import json
import os
import urllib.error
import urllib.parse
import urllib.request

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from flask import Blueprint, Response

from ckanext.episerve_theme import lineage, model_card, signing


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


# The API server inside the cluster (for the lineage tab) and its public address (for the "as JSON" link).
API_INTERNAL_URL = os.environ.get("EPISERVE_API_INTERNAL_URL", "http://episerve-api-server.default.svc.cluster.local")
API_PUBLIC_URL = os.environ.get("EPISERVE_API_PUBLIC_URL", "https://api.episerve.zib.de")
DOIP_NAMESPACE = os.environ.get("DOIP_PUBLIC_URL", "https://doip.episerve.zib.de").rstrip("/")


def _json(data, status=200):
    return Response(json.dumps(data), status=status, content_type="application/json",
                    headers={"Cache-Control": "public, max-age=300"} if status == 200 else None)


def lineage_view(qid):
    """The lineage tab's data: the API's upstream lineage of ``qid`` as a diagram and steps (see lineage.py)."""
    if not lineage.valid_qid(qid):
        return _json({"error": "not a QID"}, 400)
    query = urllib.parse.urlencode({"object": qid.upper()})
    url = f"{API_INTERNAL_URL.rstrip('/')}/lineage/events?{query}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            result = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _json({"error": f"no lineage for {qid.upper()}"}, 404)
        return _json({"error": f"lineage service answered {e.code}"}, 502)
    except Exception:
        return _json({"error": "lineage service unavailable"}, 502)
    return _json(lineage.view(result, DOIP_NAMESPACE))


class EPIServeThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.ITemplateHelpers)

    def get_helpers(self):
        return {
            "episerve_signed_url": episerve_signed_url,
            "episerve_model_card": model_card.model_card,
            "episerve_is_card_extra": lambda key: key in model_card.CARD_EXTRAS,
            "episerve_lineage_qid": lineage.qid_for,
            "episerve_lineage_api_url": lambda qid: f"{API_PUBLIC_URL.rstrip('/')}/lineage/events?object={qid}",
        }

    def update_config(self, config):
        toolkit.add_template_directory(config, "templates")
        toolkit.add_resource("fanstatic", "episerve_theme")

    def get_blueprint(self):
        bp = Blueprint("episerve_theme", __name__)
        bp.add_url_rule(
            "/metabase-proxy/<card_id>",
            view_func=metabase_proxy,
        )
        bp.add_url_rule("/lineage-view/<qid>", view_func=lineage_view)
        return bp
