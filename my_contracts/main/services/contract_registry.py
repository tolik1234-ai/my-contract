from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from django.conf import settings

from ..models import ContractDeployment


@dataclass(frozen=True)
class ContractTemplate:
    identifier: str
    display_name: str
    manifest_path: Optional[Path] = None
    description: str = ""
    default_networks: Optional[List[str]] = None
    entrypoint: Optional[Path] = None


# A short curated fallback list to keep UI operational until the external repo is mounted
_FALLBACK_CONTRACTS: List[ContractTemplate] = [
    ContractTemplate(
        identifier="time_locked_vault",
        display_name="Time Locked Vault",
        description="Смарт контракт для поэтапного выпуска токенов или казначейских средств.",
        default_networks=["ethereum", "polygon", "arbitrum"],
    ),
    ContractTemplate(
        identifier="staking_pool",
        display_name="Staking Pool",
        description="Пул с настраиваемой доходностью для программы лояльности.",
        default_networks=["ethereum", "base"],
    ),
    ContractTemplate(
        identifier="dao_treasury",
        display_name="DAO Treasury Multisig",
        description="Шаблон мультисиг кошелька с ежегодным обновлением ролей.",
        default_networks=["ethereum", "polygon", "gnosis"],
    ),
]


def _repository_root() -> Optional[Path]:
    candidate = Path(settings.BASE_DIR) / "external" / "smart-ultra-deployer"
    if candidate.exists():
        return candidate
    return None


def _load_manifest(path: Path) -> Optional[Dict[str, object]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _scan_contracts(repo_root: Path) -> List[ContractTemplate]:
    manifests = list(repo_root.rglob("manifest.json"))
    if not manifests:
        return []

    templates: List[ContractTemplate] = []
    for manifest_path in manifests:
        manifest = _load_manifest(manifest_path)
        if manifest is None:
            continue
        identifier = str(manifest.get("id") or manifest.get("slug") or manifest_path.parent.name)
        display_name = str(manifest.get("name") or identifier.replace("_", " ").title())
        description = str(manifest.get("description") or "")
        networks = manifest.get("networks") or manifest.get("supportedNetworks")
        if isinstance(networks, str):
            networks = [networks]
        if isinstance(networks, Iterable):
            networks = [str(item) for item in networks]
        else:
            networks = None
        entrypoint = None
        if "entrypoint" in manifest:
            entrypoint_candidate = manifest_path.parent / str(manifest["entrypoint"])
            if entrypoint_candidate.exists():
                entrypoint = entrypoint_candidate
        templates.append(
            ContractTemplate(
                identifier=identifier,
                display_name=display_name,
                manifest_path=manifest_path,
                description=description,
                default_networks=networks,
                entrypoint=entrypoint,
            )
        )
    return templates


_catalog_cache: Optional[List[ContractTemplate]] = None


def get_contract_catalog() -> List[ContractTemplate]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    repo_root = _repository_root()
    if repo_root:
        templates = _scan_contracts(repo_root)
        if templates:
            _catalog_cache = templates
            return templates
    _catalog_cache = _FALLBACK_CONTRACTS
    return _catalog_cache


def get_network_choices() -> List[tuple[str, str]]:
    catalog = get_contract_catalog()
    networks: List[str] = []
    for template in catalog:
        if template.default_networks:
            networks.extend(template.default_networks)
    if not networks:
        networks = ["ethereum", "polygon", "arbitrum", "base"]
    unique = []
    for network in networks:
        normalized = network.lower()
        if normalized not in unique:
            unique.append(normalized)
    return [(item, item.replace("_", " ").title()) for item in unique]


def parse_parameters(raw_value: str) -> Dict[str, object]:
    try:
        data = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("Невалидный JSON. Проверьте синтаксис параметров.") from exc
    if not isinstance(data, dict):
        raise ValueError("Параметры конструктора должны быть объектом JSON.")
    return data


def _deployment_script(repo_root: Path) -> Optional[Path]:
    candidates = [
        repo_root / "deploy.py",
        repo_root / "scripts" / "deploy.py",
        repo_root / "scripts" / "deploy_contract.py",
        repo_root / "cli" / "deploy.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def enqueue_deployment(deployment: ContractDeployment, template: ContractTemplate) -> None:
    repo_root = _repository_root()
    if repo_root is None:
        deployment.mark_simulated(
            "Репозиторий смарт-контрактов не найден. Склонируйте его в external/smart-ultra-deployer."
        )
        return

    script = _deployment_script(repo_root)
    if script is None:
        deployment.mark_simulated(
            "Не удалось найти deploy.py внутри smart-ultra-deployer. Проверьте инструкции в README."
        )
        return

    params_file = deployment.build_arguments_file(repo_root)
    deployment.status = deployment.Status.RUNNING
    deployment.status_message = 'Executing deployment script…'
    deployment.save(update_fields=['status', 'status_message', 'updated_at'])
    command = [
        "python",
        str(script),
        "--contract",
        template.identifier,
        "--network",
        deployment.network,
        "--params",
        str(params_file),
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        deployment.mark_failed("Python не найден в окружении сервера деплоя.")
        return
    except subprocess.CalledProcessError as exc:
        message = exc.stderr or exc.stdout or "Неизвестная ошибка деплоя."
        deployment.mark_failed(message)
        try:
            params_file.unlink(missing_ok=True)
        except OSError:
            pass
        return

    output = completed.stdout.strip()
    tx_hash = _extract_transaction_hash(output)
    deployment.mark_success(tx_hash=tx_hash, raw_output=output)
    try:
        params_file.unlink(missing_ok=True)
    except OSError:
        pass


def _extract_transaction_hash(output: str) -> Optional[str]:
    match = re.search(r"0x[a-fA-F0-9]{32,}", output)
    if match:
        return match.group(0)
    return None


def reset_cache() -> None:
    global _catalog_cache
    _catalog_cache = None
