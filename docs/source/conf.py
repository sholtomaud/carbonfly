# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

sys.path.insert(0, os.path.abspath("../../"))

import carbonfly

project = 'Carbonfly'
copyright = '2025, Qirui Huang'
author = 'Qirui Huang'
version = carbonfly.__version__
release = carbonfly.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.linkcode'
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
    "logo_only": True,
}
html_static_path = ['_static']

html_context = {
    "display_github": True,
    "github_user": "RWTH-E3D",
    "github_repo": "carbonfly",
    "github_version": "master",
    "conf_py_path": "/docs/source/",
}

html_css_files = [
    'custom.css',
]

html_logo = "_static/carbonfly_logo.svg"


# Prevent import errors from halting the building process
# when some external dependencies cannot be imported at build time
autodoc_mock_imports = [
    "Rhino"
]


# link code
import inspect

def linkcode_resolve(domain, info):
    if domain != 'py':
        return None

    module_name = info['module']
    fullname = info['fullname']

    try:
        mod = sys.modules.get(module_name)
        if mod is None:
            __import__(module_name)
            mod = sys.modules[module_name]

        obj = mod
        for part in fullname.split('.'):
            obj = getattr(obj, part)

        # source code location
        fn = inspect.getsourcefile(obj)
        if not fn:
            return None
        fn = os.path.relpath(fn, start=os.path.dirname(carbonfly.__file__))

        source, lineno = inspect.getsourcelines(obj)
        linespec = f"#L{lineno}-L{lineno + len(source) - 1}"

        return f"https://github.com/RWTH-E3D/carbonfly/blob/master/carbonfly/{fn}{linespec}"

    except Exception:
        return None