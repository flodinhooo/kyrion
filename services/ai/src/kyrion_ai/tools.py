"""Small explicit JSON Schema subset. Unknown constraints fail closed."""

import json

from pydantic import JsonValue

from kyrion_ai.model_contracts import ToolCall, ToolDefinition
from kyrion_ai.providers.http_stream import ProviderFailure

KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "description",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
}


def validate_schema(schema: dict[str, JsonValue], depth: int = 0) -> None:
    kind = schema.get("type")
    if not isinstance(kind, str):
        raise ProviderFailure("TOOL_CALL_INVALID")
    if (
        depth > 8
        or set(schema) - KEYS
        or schema.get("type")
        not in {
            "object",
            "array",
            "string",
            "integer",
            "number",
            "boolean",
            "null",
        }
    ):
        raise ProviderFailure("TOOL_CALL_INVALID")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ProviderFailure("TOOL_CALL_INVALID")
    for key in {
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    } & schema.keys():
        value = schema[key]
        if type(value) not in {int, float} or (
            key not in {"minimum", "maximum"} and (type(value) is not int or value < 0)
        ):
            raise ProviderFailure("TOOL_CALL_INVALID")
        if (
            (key in {"minimum", "maximum"} and kind not in {"integer", "number"})
            or (key in {"minLength", "maxLength"} and kind != "string")
            or (key in {"minItems", "maxItems"} and kind != "array")
        ):
            raise ProviderFailure("TOOL_CALL_INVALID")
    if (
        kind != "object" and {"properties", "required", "additionalProperties"} & schema.keys()
    ) or (kind != "array" and "items" in schema):
        raise ProviderFailure("TOOL_CALL_INVALID")
    if schema["type"] == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (
            not isinstance(properties, dict)
            or not isinstance(required, list)
            or any(not isinstance(key, str) or key not in properties for key in required)
            or schema.get("additionalProperties", False) is not False
        ):
            raise ProviderFailure("TOOL_CALL_INVALID")
        for child in properties.values():
            if not isinstance(child, dict):
                raise ProviderFailure("TOOL_CALL_INVALID")
            validate_schema(child, depth + 1)
    if schema["type"] == "array":
        child = schema.get("items")
        if not isinstance(child, dict):
            raise ProviderFailure("TOOL_CALL_INVALID")
        validate_schema(child, depth + 1)


def matches(value: JsonValue, schema: dict[str, JsonValue]) -> bool:
    kind = schema["type"]
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in {int, float},
        "boolean": type(value) is bool,
        "null": value is None,
    }[kind]
    if not valid or ("enum" in schema and value not in schema["enum"]):
        return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if set(value) - set(props) or any(key not in value for key in schema.get("required", [])):
            return False
        return all(matches(item, props[key]) for key, item in value.items())
    if isinstance(value, list) and not all(matches(item, schema["items"]) for item in value):
        return False
    for lower, upper, actual in [
        ("minLength", "maxLength", len(value) if isinstance(value, str) else None),
        ("minItems", "maxItems", len(value) if isinstance(value, list) else None),
        ("minimum", "maximum", value if type(value) in {int, float} else None),
    ]:
        if actual is not None and (
            (lower in schema and actual < schema[lower])
            or (upper in schema and actual > schema[upper])
        ):
            return False
    return True


def validate_call(call: ToolCall, definitions: list[ToolDefinition]) -> ToolCall:
    definition = next((tool for tool in definitions if tool.name == call.name), None)
    if definition is None or len(json.dumps(call.arguments)) > 64_000:
        raise ProviderFailure("TOOL_CALL_INVALID")
    validate_schema(definition.parameters)
    if not matches(call.arguments, definition.parameters):
        raise ProviderFailure("TOOL_CALL_INVALID")
    return call
