from ckanext.episerve_theme import labels


def test_known_keys_get_readable_names():
    assert labels.label("additional_type") == "Category"
    assert labels.label("dataset_type") == "Entry type"
    assert labels.label("source_changed_at") == "Source last changed"


def test_unknown_keys_fall_back_to_words():
    assert labels.label("some_new_field") == "Some new field"
    assert labels.label("") == ""


def test_entry_type_values_in_words():
    assert labels.value("dataset_type", "raw-data") == "Dataset"
    assert labels.value("dataset_type", "something-else") == "something-else"
    assert labels.value("additional_type", "climate") == "climate"


def test_modified_is_named_by_entry_type():
    assert labels.label("modified", "raw-data") == "Last checked"
    assert labels.label("modified", "benchmark-data") == "Generated"
    assert labels.label("modified", "model-run") == "Last processed"
    assert labels.label("modified") == "Last processed"
