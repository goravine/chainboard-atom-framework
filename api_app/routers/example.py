"""Example router — wires HTTP to the service layer through the SDK.

Demonstrates the Layer flow:

    HTTP request
        → api_app/routers/example.py (this file)
        → api_app/services/example_service.py
        → module.services.run_example_workflow
        → module/services_example.py (private child)
        → module/atoms/example_io.py (leaf operations)

The router never imports atoms directly. The scanner enforces this.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api_app.services import example_service

router = APIRouter(prefix="/api/example", tags=["example"])


@router.get("/echo/{payload}")
def echo(payload: str) -> dict:
    """Run the example workflow on a path parameter."""
    try:
        result = example_service.run(payload)
        return {"input": payload, "output": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
