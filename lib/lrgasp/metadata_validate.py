"""Functions for validating metadata"""
import re
from collections import namedtuple
import validators.url
import validators.email
from lrgasp import LrgaspException

class Field(namedtuple("Field",
                       ("name", "dtype", "element_dtype", "allow_empty", "optional", "validator"))):
    """Specify information for basic validation of a field.
    - dtype is a Python type (str, SymEnum, int, etc).  If dtype is not str,
      int, or dict, it will be converted automatically.  If it is a
      list, each entry is processed using element_dtype if it is not None
    - validator is a callable to validate the type or each element if a list.
    """
    def __new__(cls, name, dtype=str, *, element_dtype=None, allow_empty=False, optional=False, validator=None):
        if (dtype is list) and (element_dtype is None):
            raise LrgaspException("list field {name} must specify element_dtype")
        return super().__new__(cls, name, dtype, element_dtype, allow_empty, optional, validator)

def _should_convert(dtype):
    return dtype not in (str, int, dict)

def _convert_type(desc, field, dtype, val):
    try:
        return dtype(val)
    except ValueError as ex:
        raise LrgaspException(f"{desc} field {field.name} is not a valid {dtype.__name__}: {val}") from ex

def _validate_value(desc, field, val):
    try:
        field.validator(val)
    except ValueError as ex:
        raise LrgaspException(f"{desc} field {field.name} is not valid: {val}") from ex

def _check_scalar(desc, field, val):
    # returns possibly converted value
    if _should_convert(field.dtype):
        val = _convert_type(desc, field, field.dtype, val)
    elif not isinstance(val, field.dtype):
        raise LrgaspException(f"{desc} field {field.name} must be a {field.dtype.__name__}")
    if field.validator is not None:
        _validate_value(desc, field, val)
    return val

def _check_list_element(desc, field, i, val):
    # returns possibly converted value
    if _should_convert(field.element_dtype):
        val = _convert_type(desc, field, field.element_dtype, val)
    elif not isinstance(val, field.element_dtype):
        raise LrgaspException(f"{desc} field {field.name}[{i}] must be a {field.element_dtype.__name__}")
    if field.validator is not None:
        _validate_value(desc, field, val)
    return val

def _check_list(desc, field, vals):
    new_vals = []
    if not isinstance(vals, list):
        raise LrgaspException(f"{desc} field {field.name} must be a list")
    for i in range(len(vals)):
        ival = _check_list_element(desc, field, i, vals[i])
        if ival in new_vals:
            print("@1", ival)
            print("@2", new_vals)
            raise LrgaspException(f"{desc} [{i}] field {field.name} duplicate value {ival}")
        new_vals.append(ival)
    return new_vals

def _check_present_field(desc, field, obj):
    val = getattr(obj, field.name)
    if (not field.allow_empty) and (len(val) == 0):
        raise LrgaspException(f"{desc} field {field.name} must be a non-empty {field.dtype.__name__}")
    if field.dtype is list:
        val = _check_list(desc, field, val)
    else:
        val = _check_scalar(desc, field, val)
    setattr(obj, field.name, val)

def _check_missing_field(desc, field, obj):
    if not field.optional:
        raise LrgaspException(f"{desc} field {field.name} is required")

def _check_field(desc, field, obj):
    if field.name in obj:
        _check_present_field(desc, field, obj)
    else:
        _check_missing_field(desc, field, obj)

def validate_email(val):
    if validators.email(val) is not True:
        raise LrgaspException(f"invalid email address: {val}")

def validate_url(val):
    if validators.url(val, public=True) is not True:
        raise LrgaspException(f"invalid URL: {val}")

def validate_http_url(val):
    validate_url(val)
    if not (val.startswith("http:") or val.startswith("https:")):
        raise LrgaspException(f"must be an HTTP URL: {val}")

def validate_md5(val):
    "checks MD5 string"
    if not re.search("^[a-fA-F0-9]{32}$", val):
        raise LrgaspException(f"MD5 must be a 128-bit hexadecimal number: {val}")

def check_from_defs(desc, fields, obj):
    """basic check of fields given a definition table"""
    for field in fields:
        _check_field(desc, field, obj)
