Change Log
==============

Version 0.2.0
~~~~~~~~~~~~~~~
- Renamed 'Quickstart' doc to 'A short example', created a new 'Quickstart' doc which has a short code snippet that creates a figure.

- Revamped documentation, switched to new style of building documentation using only .rst files (rather than building off of Jupyter notebooks directly in RTD, which was high in memory consumption)

- Switched API to sphinx-autoapi as opposed to autodoc (moves load to local side rather than RTD generating API)

- Added new hard requirement for pillow>=8.4.0 for image manipulation

- Inspector now sets aspect ratios on map-like plots based on latitude. Rough equation but makes things like maps and raypath plots scale better

- Added Inspector, Gallery docs pages. Included some docs statements separating Pyatoa and SeisFlows3

- Added test data pertaining to docs. Docs now do not work directly with test data but rather make copies in non-repo'd directories. 

- Added __init__.py to all relevant directories that were missing it before
