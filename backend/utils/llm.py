from __future__ import annotations

import json
import inspect
from typing import get_type_hints, Callable, Any, Protocol, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionToolParam


class ToolFunction(Protocol):
    tool_spec: ChatCompletionToolParam

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def serialize_data(message_type: str, content: Any, is_dict: bool = False) -> str:
    """
    Formats data for Server-Sent Events (SSE) streaming.
    - message_type: e.g. "thought", "action", "result"
    - content: The actual data (string or dict)
    """
    if is_dict:
        if not isinstance(content, dict):
            # If it's a Pydantic model, convert to dict
            if hasattr(content, "model_dump"):
                content = content.model_dump()
            else:
                raise ValueError("content must be a dict or Pydantic model when is_dict=True")
    
    return f"data: {json.dumps({'type': message_type, 'content': content})}\n\n"


def tool_definition(desc: str) -> Callable[[Callable[..., Any]], ToolFunction]:
    """
    Decorator to create an OpenAI-compatible tool specification from a function.
    Automatically parses type hints and docstring parameter descriptions.
    """
    def decorator(func: Callable[..., Any]) -> ToolFunction:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        properties = {}
        required = []
        
        # Mapping Python types to JSON Schema types
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
                
            # Get type from hint, default to string
            p_type = type_hints.get(param_name, str)
            json_type = type_mapping.get(p_type, "string")
            
            # Extract description from docstring if it follows "param_name: description" format
            p_desc = f"The {param_name} parameter"
            doc = func.__doc__ or ""
            for line in doc.split('\n'):
                if f"{param_name}:" in line:
                    p_desc = line.split(f"{param_name}:")[1].strip()
            
            properties[param_name] = {
                "type": json_type,
                "description": p_desc
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        # Attach the tool spec to the function for easy retrieval
        tool = cast(ToolFunction, func)
        tool.tool_spec = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        }
        return tool
    return decorator


