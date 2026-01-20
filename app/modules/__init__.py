"""
Auto-discovery module loader for Paper Console.

This module automatically imports all Python modules in the modules/ directory,
which triggers their @register_module decorators to register them with the
module registry.

This allows new modules to be added without modifying any central import list.
Simply create a new file in this directory with a @register_module decorator.
"""

import importlib
import pkgutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Get the directory containing this file
package_dir = Path(__file__).parent

# Auto-discover and import all modules in this package
for finder, name, ispkg in pkgutil.iter_modules([str(package_dir)]):
    # Skip private modules (those starting with underscore)
    if not name.startswith("_"):
        try:
            importlib.import_module(f".{name}", __package__)
            logger.debug(f"Auto-imported module: {name}")
        except Exception as e:
            logger.warning(f"Failed to import module '{name}': {e}")
