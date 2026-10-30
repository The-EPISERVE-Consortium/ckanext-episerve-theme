from ckanext.episerve_theme import dates


def _pkg(created=None):
    extras = [{"key": "docker_tag", "value": "latest"}]
    if created is not None:
        extras.append({"key": "created", "value": created})
    return {"metadata_created": "2026-10-29T22:14:35.185274", "extras": extras}


def test_the_objects_own_creation_time_replaces_ckans():
    assert dates.with_created(_pkg("2026-09-02T20:27:56Z"))["metadata_created"] == "2026-09-02T20:27:56"
    assert dates.created_for(_pkg("2026-09-02 20:27:56.123+00:00")) == "2026-09-02T20:27:56"


def test_without_a_readable_created_extra_ckans_date_stays():
    for pkg in (_pkg(), _pkg(""), _pkg("yesterday")):
        assert dates.with_created(pkg)["metadata_created"] == "2026-10-29T22:14:35.185274"
