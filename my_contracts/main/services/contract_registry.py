from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
    constructor_schema: List[Dict[str, Any]] = field(default_factory=list)
    deployment: Dict[str, Any] = field(default_factory=dict)
    artifact: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NetworkMetadata:
    slug: str
    display_name: str
    chain_id: int
    rpc_url: Optional[str] = None
    manager_address: Optional[str] = None


# A short curated fallback list to keep UI operational until the external repo is mounted
_FALLBACK_CONTRACTS: List[ContractTemplate] = [
    ContractTemplate(
        identifier="time_locked_vault",
        display_name="Time Locked Vault",
        description="Смарт контракт для поэтапного выпуска токенов или казначейских средств.",
        default_networks=["sepolia", "polygon"],
        constructor_schema=[
            {
                "name": "beneficiary",
                "type": "address",
                "label": "Beneficiary",
                "placeholder": "0x0000…",
                "description": "Получатель средств после наступления времени разблокировки.",
            },
            {
                "name": "unlockTime",
                "type": "uint256",
                "label": "Unlock timestamp",
                "placeholder": "1700000000",
                "description": "UNIX время, когда сокровищница станет доступной.",
            },
        ],
        deployment={
            "method": "deployTemplate",
            "event": "VaultDeployed",
            "argumentSchema": "abi.encode(beneficiary, unlockTime)",
        },
    ),
    ContractTemplate(
        identifier="staking_pool",
        display_name="Staking Pool",
        description="Пул с настраиваемой доходностью для программы лояльности.",
        default_networks=["sepolia", "base"],
        constructor_schema=[
            {
                "name": "token",
                "type": "address",
                "label": "ERC20 token",
                "description": "Адрес токена, который будет принимать пул.",
            },
            {
                "name": "rewardRate",
                "type": "uint256",
                "label": "Reward per block",
                "placeholder": "1000000000000000",
            },
        ],
        deployment={
            "method": "deployTemplate",
            "event": "PoolDeployed",
            "argumentSchema": "abi.encode(token, rewardRate)",
        },
    ),
    ContractTemplate(
        identifier="dao_treasury",
        display_name="DAO Treasury Multisig",
        description="Шаблон мультисиг кошелька с ежегодным обновлением ролей.",
        default_networks=["sepolia", "polygon"],
        constructor_schema=[
            {
                "name": "owners",
                "type": "address[]",
                "label": "Owners",
                "description": "Список кошельков с правом подписи.",
            },
            {
                "name": "threshold",
                "type": "uint256",
                "label": "Signature threshold",
                "placeholder": "2",
            },
        ],
        deployment={
            "method": "deployTemplate",
            "event": "TreasuryDeployed",
            "argumentSchema": "abi.encode(owners, threshold)",
        },
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


def _parse_constructor_schema(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    schema_source: Any = (
        manifest.get("constructor")
        or manifest.get("parameters")
        or manifest.get("inputs")
        or []
    )
    if isinstance(schema_source, dict):
        schema_source = (
            schema_source.get("fields")
            or schema_source.get("inputs")
            or schema_source.get("parameters")
            or []
        )

    result: List[Dict[str, Any]] = []
    if not isinstance(schema_source, Iterable) or isinstance(schema_source, (str, bytes)):
        return result

    for field in schema_source:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or field.get("key") or "")
        if not name:
            continue
        result.append(
            {
                "name": name,
                "type": str(field.get("type") or "bytes"),
                "label": str(field.get("label") or name.replace("_", " ").title()),
                "placeholder": field.get("placeholder", ""),
                "description": field.get("description", ""),
                "required": field.get("required", True),
                "default": field.get("default"),
            }
        )
    return result


def _resolve_artifact(manifest_path: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    artifact_spec: Any = manifest.get("artifact") or manifest.get("artifactPath")
    artifact_info: Dict[str, Any] = {}

    if isinstance(artifact_spec, str):
        artifact_spec = {"path": artifact_spec}
    if isinstance(artifact_spec, dict):
        path_value = artifact_spec.get("path") or artifact_spec.get("file")
        if isinstance(path_value, str):
            candidate = manifest_path.parent / path_value
            if candidate.exists():
                loaded = _load_manifest(candidate)
                if loaded:
                    artifact_info["path"] = str(candidate)
                    artifact_info["abi"] = loaded.get("abi")
                    artifact_info["bytecode"] = (
                        loaded.get("bytecode")
                        or loaded.get("bytecodeFull")
                        or loaded.get("data")
                    )
    if not artifact_info.get("abi") and isinstance(manifest.get("abi"), list):
        artifact_info["abi"] = manifest["abi"]
    if not artifact_info.get("bytecode") and isinstance(manifest.get("bytecode"), str):
        artifact_info["bytecode"] = manifest["bytecode"]
    return artifact_info


def _build_deployment_config(
    manifest: Dict[str, Any], artifact: Dict[str, Any]
) -> Dict[str, Any]:
    raw_config: Any = (
        manifest.get("deploy")
        or manifest.get("deployment")
        or manifest.get("manager")
        or {}
    )
    if not isinstance(raw_config, dict):
        raw_config = {}
    config = dict(raw_config)

    managers = config.get("managers") or manifest.get("managers")
    if isinstance(managers, dict):
        normalized = {
            str(key).lower(): str(value)
            for key, value in managers.items()
            if value
        }
        config["managers"] = normalized
    elif isinstance(managers, str):
        config["managers"] = {"default": managers}

    config.setdefault("method", config.get("function") or "deployTemplate")
    config.setdefault("event", manifest.get("event"))
    if artifact.get("abi") and not config.get("abi"):
        config["abi"] = artifact["abi"]
    if artifact.get("bytecode") and not config.get("bytecode"):
        config["bytecode"] = artifact["bytecode"]
    return config


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
        constructor_schema = _parse_constructor_schema(manifest)
        artifact = _resolve_artifact(manifest_path, manifest)
        deployment_config = _build_deployment_config(manifest, artifact)

        templates.append(
            ContractTemplate(
                identifier=identifier,
                display_name=display_name,
                manifest_path=manifest_path,
                description=description,
                default_networks=networks,
                entrypoint=entrypoint,
                constructor_schema=constructor_schema,
                deployment=deployment_config,
                artifact=artifact,
            )
        )
    return templates


_catalog_cache: Optional[List[ContractTemplate]] = None
_network_cache: Optional[List[NetworkMetadata]] = None


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


_NETWORK_LABELS: Dict[str, str] = {
    "ethereum": "Ethereum Mainnet",
    "polygon": "Polygon",
    "arbitrum": "Arbitrum One",
    "base": "Base",
    "sepolia": "Sepolia Testnet",
    "mumbai": "Polygon Mumbai",
}


def _normalize_networks(networks: Iterable[str]) -> List[str]:
    result: List[str] = []
    for network in networks:
        normalized = str(network).lower().strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def get_network_choices() -> List[tuple[str, str]]:
    catalog = get_contract_catalog()
    networks: List[str] = []
    for template in catalog:
        if template.default_networks:
            networks.extend(template.default_networks)
    if not networks:
        networks = list(settings.DEPLOY_MANAGER_CONFIG.keys()) or ["sepolia"]
    unique = _normalize_networks(networks)
    if not unique:
        unique = ["sepolia"]
    return [
        (item, _NETWORK_LABELS.get(item, item.replace("_", " ").title()))
        for item in unique
    ]


def get_network_metadata(include_all: bool = False) -> List[NetworkMetadata]:
    global _network_cache
    if _network_cache is not None and not include_all:
        return _network_cache

    config = getattr(settings, "DEPLOY_MANAGER_CONFIG", {}) or {}
    if include_all:
        network_slugs = list(config.keys())
    else:
        network_slugs = _normalize_networks(
            network
            for template in get_contract_catalog()
            for network in (template.default_networks or [])
        )
        if not network_slugs:
            network_slugs = list(config.keys())
    if not network_slugs:
        network_slugs = ["sepolia"]

    metadata: List[NetworkMetadata] = []
    for slug in network_slugs:
        entry = config.get(slug, {})
        chain_id_raw = entry.get("chain_id")
        try:
            chain_id = int(chain_id_raw) if chain_id_raw else 0
        except (TypeError, ValueError):
            chain_id = 0
        metadata.append(
            NetworkMetadata(
                slug=slug,
                display_name=_NETWORK_LABELS.get(
                    slug, slug.replace("_", " ").title()
                ),
                chain_id=chain_id,
                rpc_url=entry.get("rpc_url"),
                manager_address=(entry.get("manager") or None),
            )
        )

    if not include_all:
        _network_cache = metadata
    return metadata


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
    global _network_cache
    _catalog_cache = None
    _network_cache = None


def template_to_payload(template: ContractTemplate) -> Dict[str, Any]:
    return {
        "id": template.identifier,
        "name": template.display_name,
        "description": template.description,
        "networks": _normalize_networks(template.default_networks or []),
        "constructor": template.constructor_schema,
        "deployment": template.deployment,
        "artifact": template.artifact,
    }


def build_catalog_payload() -> Dict[str, Any]:
    catalog = get_contract_catalog()
    templates_payload = [template_to_payload(item) for item in catalog]
    networks_payload = [
        {
            "slug": item.slug,
            "name": item.display_name,
            "chainId": item.chain_id,
            "rpcUrl": item.rpc_url,
            "manager": item.manager_address,
        }
        for item in get_network_metadata()
    ]
    return {
        "templates": templates_payload,
        "networks": networks_payload,
    }
