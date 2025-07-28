from sqlalchemy import MetaData, Table

_table_cache = {}

def get_table(table_name, schema_name, bind):
    key = (schema_name, table_name)
    if key not in _table_cache:
        metadata = MetaData(schema=schema_name)
        _table_cache[key] = Table(table_name, metadata, autoload_with=bind)
    return _table_cache[key] 