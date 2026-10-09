"""Shared token-preserving E1 encoding, independent of database/runtime dependencies."""
import hashlib
import json
import re
from .errors import Fault,require,missing

class Number(str):
    """A validated JSON numeric token, not a JSON string."""

def parse(raw):
    def pairs(items):
        obj={}
        for key,value in items:
            require(key not in obj,'VALIDATION_ERROR','Duplicate JSON member.')
            obj[key]=value
        return obj
    def invalid(value):raise Fault('VALIDATION_ERROR','Nonfinite JSON token.')
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_int=Number,parse_float=Number,parse_constant=invalid)
        e1(value)  # Validate Unicode, including escaped lone surrogates.
        return value
    except (ValueError,UnicodeError,RecursionError):
        raise Fault('VALIDATION_ERROR','Invalid bounded JSON value.') from None

def e1(value):
    if isinstance(value,Number):
        require(re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?',value) is not None,'VALIDATION_ERROR','Invalid numeric token.')
        return str(value)
    if value is None:return 'null'
    if type(value) is bool:return 'true' if value else 'false'
    if type(value) is int:return str(value)
    if isinstance(value,str):
        value.encode('utf-8',errors='strict')
        return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    if isinstance(value,list):return '['+','.join(e1(x) for x in value)+']'
    if isinstance(value,dict):
        require(all(isinstance(k,str) for k in value),'VALIDATION_ERROR','JSON keys must be strings.')
        return '{'+','.join(e1(k)+':'+e1(value[k]) for k in sorted(value))+'}'
    raise Fault('VALIDATION_ERROR','Use source numeric tokens, never binary floats.')

def digest(value):return hashlib.sha256(e1(value).encode('utf-8')).hexdigest()
def literal_type(value):
    if isinstance(value,Number):return 'integer' if not any(x in value for x in '.eE') else 'number'
    if value is None:return 'null'
    return {bool:'boolean',int:'integer',str:'string',list:'array',dict:'object'}[type(value)]

def pointer(value,selector):
    if selector=='':return value
    require(selector.startswith('/'),'VALIDATION_ERROR','Use an RFC6901 payload pointer.')
    for token in selector[1:].split('/'):
        require(re.search(r'~(?![01])',token) is None,'VALIDATION_ERROR','Invalid pointer escape.')
        key=token.replace('~1','/').replace('~0','~')
        if isinstance(value,dict):
            if key not in value:missing()
            value=value[key]
        elif isinstance(value,list):
            require(re.fullmatch(r'0|[1-9][0-9]*',key) is not None,'VALIDATION_ERROR','Invalid array pointer.')
            if int(key)>=len(value):missing()
            value=value[int(key)]
        else:missing()
    return value

