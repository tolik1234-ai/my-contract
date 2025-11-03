from __future__ import annotations

from .services.contract_registry import get_contract_catalog


def contract_sidebar(request):
    catalog = get_contract_catalog()
    return {
        "sidebar_contracts": catalog[:6],
    }
