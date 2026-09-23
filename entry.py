"""Entry point for the frozen (PyInstaller) build.

PyInstaller executes the script it is handed as a top-level ``__main__`` with
no package context, so ``__package__`` is empty and the relative imports in
``paperharvest/__main__.py`` raise::

    ImportError: attempted relative import with no known parent package

Importing the package properly first fixes that. Running from source does not
need this file -- ``python -m paperharvest`` and the ``paperharvest`` console
script both resolve ``paperharvest.__main__`` as a real submodule.
"""

from paperharvest.__main__ import main

main()
