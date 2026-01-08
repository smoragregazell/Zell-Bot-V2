"""
Tool response utilities for V1 compatibility.
This module provides response formatting functions used by legacy V1 tools.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ToolResponse(BaseModel):
    """
    Standardized response format for V1 tools.
    Note: V2 uses dict responses directly, not this model.
    """
    classification: str
    response: str
    error: Optional[str] = ""
    results: Optional[list] = []


def make_error_response(error_message: str) -> Dict[str, Any]:
    """
    Creates a standardized error response.
    Used by V1 tools for error handling.
    """
    return {
        "classification": "Error",
        "response": "",
        "error": error_message,
        "results": []
    }

