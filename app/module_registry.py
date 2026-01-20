"""
Module Registry System for Paper Console.

This module provides a self-registering mechanism for printer modules.
New modules can use the @register_module decorator to automatically
register themselves with the system, eliminating the need to modify
main.py or any other files.

Example usage:
    from app.module_registry import register_module

    @register_module(
        type_id="my_module",
        label="My Cool Module",
        description="Does something awesome",
        icon="star",
        offline=True,
    )
    def format_my_module_receipt(printer, config, module_name):
        printer.print_header(module_name or "MY MODULE")
        printer.print_body("Hello from my module!")
        printer.print_line()
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, List
import logging
try:
    import jsonschema
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


logger = logging.getLogger(__name__)


@dataclass
class ModuleDefinition:
    """
    Metadata for a registered module type.
    
    Attributes:
        type_id: Unique identifier for the module type (e.g., "weather", "quotes")
        label: Human-readable name shown in the UI (e.g., "Weather Forecast")
        description: Brief description of what the module does
        icon: Icon name for the UI (matches Phosphor icon names)
        offline: Whether the module works without internet
        execute_fn: The function to call when printing (format_xxx_receipt)
        config_schema: JSON Schema for generating config forms (optional)
        ui_schema: UI Schema for customizing form rendering (optional)
        config_class: Pydantic config class if the module uses one (optional)
        category: For grouping in UI (e.g., "content", "games", "utilities")
    """
    type_id: str
    label: str
    description: str
    icon: str
    offline: bool
    execute_fn: Callable
    config_schema: Optional[Dict[str, Any]] = None
    ui_schema: Optional[Dict[str, Any]] = None
    config_class: Optional[type] = None
    category: str = "general"


# Global registry of all modules
_registry: Dict[str, ModuleDefinition] = {}


def register_module(
    type_id: str,
    label: str,
    description: str = "",
    icon: str = "file",
    offline: bool = True,
    config_schema: Optional[Dict[str, Any]] = None,
    ui_schema: Optional[Dict[str, Any]] = None,
    config_class: Optional[type] = None,
    category: str = "general",
):
    """
    Decorator to register a module with the system.
    
    Usage:
        @register_module(
            type_id="weather",
            label="Weather Forecast",
            description="Current conditions and 7-day forecast",
            icon="sun",
            offline=False,
            config_schema={...},
        )
        def format_weather_receipt(printer, config, module_name):
            ...
    
    Args:
        type_id: Unique identifier for the module type
        label: Human-readable name shown in the UI
        description: Brief description of what the module does
        icon: Icon name for the UI
        offline: Whether the module works without internet
        config_schema: JSON Schema for config form generation (optional)
        ui_schema: UI Schema for customizing form rendering (optional)
        config_class: Pydantic config class (optional)
        category: Grouping category for UI (optional)
    
    Returns:
        Decorator function that registers the module and returns the original function
    """
    def decorator(fn: Callable) -> Callable:
        if type_id in _registry:
            logger.warning(f"Module '{type_id}' is already registered. Overwriting.")
        
        _registry[type_id] = ModuleDefinition(
            type_id=type_id,
            label=label,
            description=description,
            icon=icon,
            offline=offline,
            execute_fn=fn,
            config_schema=config_schema,
            ui_schema=ui_schema,
            config_class=config_class,
            category=category,
        )
        logger.debug(f"Registered module: {type_id}")
        return fn
    
    return decorator


def get_module(type_id: str) -> Optional[ModuleDefinition]:
    """
    Get a module definition by its type ID.
    
    Args:
        type_id: The module type identifier
        
    Returns:
        ModuleDefinition if found, None otherwise
    """
    return _registry.get(type_id)


def get_all_modules() -> Dict[str, ModuleDefinition]:
    """
    Get a copy of all registered modules.
    
    Returns:
        Dictionary mapping type_id to ModuleDefinition
    """
    return _registry.copy()


def list_module_types() -> List[Dict[str, Any]]:
    """
    Get a list of all module types suitable for API responses.
    
    Returns:
        List of dicts with module metadata for the frontend
    """
    modules = []
    for type_id, defn in _registry.items():
        modules.append({
            "id": defn.type_id,
            "label": defn.label,
            "description": defn.description,
            "icon": defn.icon,
            "offline": defn.offline,
            "category": defn.category,
            "configSchema": defn.config_schema,
            "uiSchema": defn.ui_schema,
        })
    return modules


def execute_module_by_type(
    module_type: str,
    printer,
    config: Dict[str, Any],
    module_name: str,
) -> bool:
    """
    Execute a module by its type ID.
    
    This is the main entry point for running modules from the dispatch system.
    
    Args:
        module_type: The module type identifier (e.g., "weather", "quotes")
        printer: The printer driver instance
        config: Module configuration dictionary
        module_name: Display name for the module header
        
    Returns:
        True if the module executed successfully, False otherwise
    """
    defn = _registry.get(module_type)
    
    if defn is None:
        logger.warning(f"Unknown module type: {module_type}")
        return False
    
    try:
        # All modules follow the signature: (printer, config, module_name)
        # Some may use config differently (e.g., email uses 'messages' parameter)
        # but the standard call works for most modules
        defn.execute_fn(printer, config, module_name)
        return True
    except Exception as e:
        logger.error(f"Error executing module '{module_type}': {e}", exc_info=True)
        return False



def validate_module_config(module_type: str, config: Dict[str, Any]) -> None:
    """
    Validate a module configuration against its registered schema.
    
    Args:
        module_type: The module type identifier
        config: The configuration dictionary to validate
        
    Raises:
        ValueError: If the module type is unknown or validation fails
    """
    defn = _registry.get(module_type)
    if defn is None:
        raise ValueError(f"Unknown module type: {module_type}")
        
    if defn.config_schema:
        if not HAS_JSONSCHEMA:
            logger.warning(f"jsonschema not installed. Skipping validation for {module_type}.")
            return
            
        try:
            validate(instance=config, schema=defn.config_schema)
        except ValidationError as e:
            path = ".".join(str(p) for p in e.path) if e.path else "root"
            raise ValueError(f"Invalid configuration for {module_type} at '{path}': {e.message}")


def is_registered(type_id: str) -> bool:
    """Check if a module type is registered."""
    return type_id in _registry


def get_registry_stats() -> Dict[str, Any]:
    """Get statistics about the registry for debugging."""
    return {
        "total_modules": len(_registry),
        "module_types": list(_registry.keys()),
        "offline_modules": [m.type_id for m in _registry.values() if m.offline],
        "online_modules": [m.type_id for m in _registry.values() if not m.offline],
    }
