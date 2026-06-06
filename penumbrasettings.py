import os
import json
from typing import List, Any, Optional

def get_penumbral_settings_path() -> str:
    """Return the path to the Penumbra settings file."""

    data_path = os.getenv('APPDATA')
    settings_path = os.path.join(data_path, 'XIVLauncher', 'pluginConfigs', 'Penumbra', 'collections')

    return settings_path

def get_sort_order_path() -> str:
    """Return the path to the Penumbra sort_order.json file."""
    data_path = os.getenv('APPDATA')
    return os.path.join(data_path, 'XIVLauncher', 'pluginConfigs', 'Penumbra', 'sort_order.json')

def get_collections_path() -> str:
    folders = []
    for files in os.listdir(get_penumbral_settings_path()):
        if files.endswith('.json'):
            folders.append(os.path.join(get_penumbral_settings_path(), files))
    return folders

def _load_json_utf8_sig(path: str) -> Optional[Any]:
    """Load JSON from path with UTF-8 BOM handling.

    Returns None for empty or invalid JSON files instead of raising.
    """
    try:
        with open(path, 'rb') as fb:
            raw = fb.read()
        if not raw:
            return None
        text = raw.decode('utf-8-sig', errors='replace')
        if not text.strip():
            return None
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Warning: Skipping invalid JSON file '{path}': {e}")
        return None
    except Exception as e:
        print(f"Warning: Could not read '{path}': {e}")
        return None


def get_mod_configs(mod_name: Optional[str] = None) -> List[dict]:
    """Return Penumbra mod configurations from all collections.

    Args:
        mod_name: If provided, return only settings for this specific mod.
                  Otherwise, return all mod settings from all collections.

    Returns:
        List of dicts with collection info and mod settings.
        Format: [{"collection": "Name", "mod": "ModName", "settings": {...}, "enabled": bool, "priority": int}, ...]
    """
    collections = get_collections_path()
    configs: List[dict] = []
    for collection in collections:
        jconfig = _load_json_utf8_sig(collection)
        if jconfig is not None:
            collection_name = jconfig.get('Name', 'Unknown')
            mod_settings = jconfig.get('Settings', {})
            
            for mod, mod_data in mod_settings.items():
                if mod_name is None or mod == mod_name:
                    configs.append({
                        'collection': collection_name,
                        'mod': mod,
                        'settings': mod_data.get('Settings', {}),
                        'enabled': mod_data.get('Enabled', False),
                        'priority': mod_data.get('Priority', 0)
                    })
    return configs

def clone_config(original: str, target: str) -> bool:
    """Clone a Penumbra mod configuration from original mod to target mod.

    Searches all collection JSON files and clones settings/enabled/priority
    from the original mod name to the target mod name. Priority is increased by 1.
    Also clones the internal path from sort_order.json.

    Args:
        original: Name of the original mod to clone from.
        target: Name of the target mod to clone to.

    Returns:
        True if at least one collection was updated, False otherwise.
    """
    collections = get_collections_path()
    success = False
    for collection in collections:
        jconfig = _load_json_utf8_sig(collection)
        if jconfig is not None:
            mod_settings = jconfig.get('Settings', {})
            if original in mod_settings:
                # Deep copy the original mod's data
                import copy
                original_data = copy.deepcopy(mod_settings[original])
                
                # Increase priority by 1
                if 'Priority' in original_data:
                    original_data['Priority'] = original_data['Priority'] + 1
                
                mod_settings[target] = original_data
                jconfig['Settings'] = mod_settings
                
                # Preserve BOM if present
                try:
                    with open(collection, 'rb') as fb:
                        raw = fb.read()
                    has_bom = raw.startswith(b'\xef\xbb\xbf')
                    
                    temp_path = collection + '.tmp'
                    with open(temp_path, 'w', encoding=('utf-8-sig' if has_bom else 'utf-8')) as f:
                        json.dump(jconfig, f, indent=2, ensure_ascii=False)
                    os.replace(temp_path, collection)
                    success = True
                except Exception as e:
                    print(f"Error writing to '{collection}': {e}")
    
    # Clone internal path from sort_order.json
    try:
        sort_order_path = get_sort_order_path()
        if os.path.exists(sort_order_path):
            sort_order = _load_json_utf8_sig(sort_order_path)
            if sort_order is not None:
                data = sort_order.get('Data', {})
                if original in data:
                    # Clone the internal path
                    import copy
                    data[target] = copy.deepcopy(data[original])
                    sort_order['Data'] = data
                    
                    # Write back to sort_order.json
                    with open(sort_order_path, 'rb') as fb:
                        raw = fb.read()
                    has_bom = raw.startswith(b'\xef\xbb\xbf')
                    
                    temp_path = sort_order_path + '.tmp'
                    with open(temp_path, 'w', encoding=('utf-8-sig' if has_bom else 'utf-8')) as f:
                        json.dump(sort_order, f, indent=2, ensure_ascii=False)
                    os.replace(temp_path, sort_order_path)
                    success = True
    except Exception as e:
        print(f"Error cloning internal path entry: {e}")
    
    return success

