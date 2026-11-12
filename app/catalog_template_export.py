"""Safe XLSX serialization for existing catalog records (no database writes)."""
from datetime import date, datetime, time
from decimal import Decimal


def excel_value(value):
    if value is None:
        return ''
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode('utf-8', errors='replace')
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_catalog_workbook(headers, records, workbook_class):
    workbook = workbook_class()
    sheet = workbook.active
    sheet.title = 'Catalog'
    sheet.append(list(headers))
    for record in records:
        row = dict(record)
        sheet.append([excel_value(row.get(name)) for name in headers])
    instructions = workbook.create_sheet('Instructions')
    instructions.append(['Use stable product ID. status = live, coming_soon, or archived. Existing IDs update; new IDs insert. Missing rows are never deleted.'])
    return workbook
