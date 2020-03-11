#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Tangelo Web Framework documentation build configuration file, created by
# sphinx-quickstart on Thu Apr 11 11:42:23 2013.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

from __future__ import print_function
import sys, os
import subprocess
import glob
import shlex
import shutil
import tempfile

# First we need to create the jupyter links from gms to Notebooks

#
# copy jupyter notebook htmls
#
#if not os.path.exists("Jupyter-notebooks"):
#    os.system("git clone https://github.com/CDAT/Jupyter-notebooks.git")

tmp_dir = tempfile.mkdtemp()
print("XXX tmp_dir: {d}".format(d=tmp_dir))

tmp_notebooks_dir = os.path.join(tmp_dir, "Jupyter-notebooks")
os.system("git clone https://github.com/CDAT/Jupyter-notebooks.git {d}".format(d=tmp_dir))

jupyter_htmls = glob.glob(os.path.join(tmp_notebooks_dir, "vcs", "*", "*html"))
jupyter_html_dirs = glob.glob(os.path.join(tmp_notebooks_dir, "vcs", "*"))

notebook_htmls_dir = os.path.join("static")
if not os.path.exists(notebook_htmls_dir):
    os.makedirs(notebook_htmls_dir)

for j in jupyter_html_dirs:
    dir_name = os.path.basename(j)
    dest_dir = os.path.join(notebook_htmls_dir, dir_name)
    if not os.path.exists(dest_dir):
        shutil.copytree(j, dest_dir)

shutil.rmtree(tmp_dir)

#import sphinx_bootstrap_theme

"""
# on_rtd is whether we are on readthedocs.org
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme
"""
html_theme = 'agogo'
#import easydev
#html_theme_path = [easydev.get_path_sphinx_themes()]

# otherwise, readthedocs.org uses their theme by default, so no need to specify it

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath(os.path.join("..", "vcs")))


# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.

extensions = [#'easydev.copybutton',
              'sphinx.ext.autodoc',
              'sphinx.ext.todo',
              'sphinx.ext.coverage',
              'sphinx.ext.mathjax',
              'sphinx.ext.ifconfig',
              'sphinx.ext.viewcode',
              'sphinx.ext.extlinks',
              'sphinx.ext.doctest',
              'sphinx.ext.intersphinx',
              'sphinx.ext.graphviz',
              'sphinx.ext.napoleon',
              'nbsphinx',
              'sphinx.ext.mathjax',
              ]

jscopybutton_path = "copybutton.js"

try:
    from easydev.copybutton import get_copybutton_path
    from easydev.copybutton import copy_javascript_into_static_path
    copy_javascript_into_static_path("_build/html/_static", get_copybutton_path())
except Exception:
    print("could not copy the copybutton javascript")


# turn off doctests of autodoc included files (these are tested elsewhere)
# doctest_test_doctest_blocks = None
doctest_path = sys.path

# Not currently doctesting VCS with sphinx due to some conflicting name errors across tests
# in the same python instance.
# Setup and cleanup might be able to fix it, but I couldn't get it to work
doctest_global_setup = """
import vcs, cdms2, os
ex = ex1 = ex2 = None
__examples = [ex, ex1, ex2]
# Copy vcs.elements so we can do a diff later.
# check if it already exists so we don't overwrite the first copy
for d in vcs.listelements("display"):
    try:
        disp = vcs.elements["display"][d]
    except:
        continue
    if disp._parent is not None:
        disp._parent.clear()
vcs.reset()
try:
    elts
except:
    elts = {}
    for key in vcs.elements.keys():
        if type(vcs.elements[key]) == dict:
            elts[key]=dict(vcs.elements[key])
        else:
            elts[key]=vcs.elements[key]
    """

doctest_global_cleanup = """
import glob, sys, vcs
for d in vcs.listelements("display"):
    try:
        disp = vcs.elements["display"][d]
    except:
        continue
    if disp._parent is not None:
        disp._parent.clear()
vcs.reset()
f=open("dt_cleanup_log", "a+", 1)
log=[]
gb = glob.glob
patterns = ["example.*", "*.json", "*.svg", "ex_*", "my*", "filename.*"]
files = []
for pattern in patterns:
    fnames = gb(pattern)
    for name in fnames:
        files.append(name)
for file in files:
    try:
        os.remove(file)
    except:
        log.append("COULD NOT delete file: " + file + "\\n")
f.writelines(log)
f.flush()
"""
# Add any paths that contain templates here, relative to this directory.
templates_path = ['templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'VCS'
copyright = u'2016, LLNL'
author = u'LLNL AIMS Team'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# These are set to None here, but this is overridden in CMakeLists.txt via -D
# flags to set them explicitly using a variable defined there.
#

# The full version, including alpha/beta/rc tags.
release = str(subprocess.Popen(['git', 'describe','--tags'],stdout=subprocess.PIPE).communicate()[0].strip())

# The short X.Y version.
version = ".".join(release.split(".")[:2])

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', '**.ipynb_checkpoints']

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []

# Define an external link to refer to the base Tangelo installation - this is
# the actual installation if the docs are built locally, or the default location
# of localhost, port 80, for the documentation built on readthedocs.
import os
on_rtd = os.environ.get("READTHEDOCS", None) is not None
extlinks = {"root": ("http://localhost:8080%s" if on_rtd else "%s", None)}

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#html_theme = 'pyramid'
#html_theme = 'bootstrap'
#html_theme_path = sphinx_bootstrap_theme.get_html_theme_path()

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = { "stickysidebar" : "true", "headerbg" : "#01796F" }

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = "tangelo.ico"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# Show "todo" notes.
todo_include_todos = False

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'vcsdoc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
'classoptions': ',oneside'
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
    ("API/vcs", 'vcs.tex', u'VCS API Documentation',
     u'AIMS Team', 'manual'),
]
# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_toplevel_sectioning = 'section'

# If true, show page references after internal links.
latex_show_pagerefs = True

# If true, show URL addresses after external links.
latex_show_urls = 'no'

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'vcs', 'VCS Documentation',
     ['LLNL'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'VCS', u'VCS Documentation',
     author, 'VCS', 'Visualization Control System',
     'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'
