def validate_item_payload(payload: dict):
    errors = []
    name = payload.get('name')
    if not name or not isinstance(name, str) or not name.strip():
        errors.append('name is required and must be a non-empty string')
    desc = payload.get('description')
    if desc is not None and not isinstance(desc, str):
        errors.append('description must be a string')
    return '; '.join(errors) if errors else None
