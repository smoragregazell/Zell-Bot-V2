# utils/tool_registry.py

TOOL_ROUTER = {}

def register_tool(name):
    def wrapper(fn):
        TOOL_ROUTER[name] = fn
        return fn
    return wrapper

def get_tool_by_classification(classification):
    return TOOL_ROUTER.get(classification)
