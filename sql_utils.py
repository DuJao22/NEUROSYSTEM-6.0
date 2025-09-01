"""
Utility functions for SQL operations and data conversion
"""

def row_to_dict(row):
    """Convert a SQLite Row object to a JSON-serializable dictionary"""
    if row is None:
        return None
    
    result = {}
    for key in row.keys():
        value = row[key]
        # Convert any special types to JSON-serializable formats
        if isinstance(value, (int, float, str, bool)) or value is None:
            result[key] = value
        else:
            # For other types, convert to string representation
            result[key] = str(value)
    return result

def rows_to_dicts(rows):
    """Convert a list of SQLite Row objects to JSON-serializable dictionaries"""
    if rows is None:
        return []
    return [row_to_dict(row) for row in rows if row is not None]

def safe_float(value, default=0.0):
    """Safely convert a value to float, with a default fallback"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert a value to int, with a default fallback"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default