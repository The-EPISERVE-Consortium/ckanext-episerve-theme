from setuptools import setup, find_packages

setup(
    name="ckanext-episerve-theme",
    version="0.1.0",
    description="CKAN theme for the EPISERVE Data Catalog",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        "ckan.plugins": [
            "episerve_theme = ckanext.episerve_theme.plugin:EPIServeThemePlugin",
        ],
        "fanstatic.libraries": [
            "episerve_theme = ckanext.episerve_theme.fanstatic:episerve_theme",
        ],
    },
)
