import structlog
from fastapi import APIRouter, HTTPException
from typing import TypedDict, Dict, List
#from typing_extensions import TypedDict, Dict, List

from proxmox_client import proxmox

router = APIRouter()
logger = structlog.get_logger()

# TypedDicts for API models
class ClusterMapping(TypedDict):
    id: str
    mdev: int
    type: str
    map: List[str]

class MdevTypeInfo(TypedDict):
    type: str
    available: int
    description: str
    name: str

class MdevProfile(TypedDict, total=False):
    name: str
    available: bool
    description: str
    attached: bool
    attached_vmids: List[int]

class GPUInfo(TypedDict, total=False):
    mdev_types: Dict[str, MdevProfile]

class MappingInfo(TypedDict):
    nodes: Dict[str, GPUInfo]

class AvailableGPUs(TypedDict):
    mappings: Dict[str, MappingInfo]

# Helpers
async def _fetch_cluster_mappings() -> List[ClusterMapping]:
    try:
        return proxmox.cluster.mapping('pci').get()
    except Exception as e:
        logger.error("Error fetching cluster PCI mappings", error=str(e))
        raise HTTPException(status_code=502, detail="Cannot fetch cluster PCI mappings")

async def _fetch_vms(node: str) -> List[dict]:
    try:
        return proxmox.nodes(node).qemu.get()
    except Exception as e:
        logger.error("Error fetching VMs on node %s: %s", node, str(e))
        raise HTTPException(status_code=502, detail=f"Cannot fetch VMs on node {node}")

async def _find_attached_mappings(
    node: str,
    vms: List[dict],
    mapping_id: str
) -> List[Dict[str, int]]:
    attached = []
    for vm in vms:
        vmid = vm.get('vmid')
        if not vmid:
            continue
        try:
            cfg = proxmox.nodes(node).qemu(vmid).config.get()
        except Exception:
            continue
        for val in cfg.values():
            if isinstance(val, str) and f"mapping={mapping_id}" in val:
                parts = dict(item.split('=', 1) for item in val.split(',') if '=' in item)
                mdev_type = parts.get('mdev')
                if mdev_type:
                    attached.append({'vmid': vmid, 'mdev': mdev_type})
    return attached

async def _process_node(
    node: str,
    instances: List[dict],
    mapping_id: str,
    max_mdevs: int
) -> GPUInfo:
    # Fetch VMs and attached vGPU mappings
    vms = await _fetch_vms(node)
    attached_list = await _find_attached_mappings(node, vms, mapping_id)

    # Determine PF root (first instance ending '.4')
    pf_path = next((inst['path'] for inst in instances if inst['path'].endswith('.4')), instances[0]['path'])

    # Fetch vGPU profiles from API
    try:
        profiles: List[MdevTypeInfo] = proxmox.nodes(node).hardware.pci(pf_path).mdev.get()
    except Exception:
        profiles = []

    # Aggregate VMIDs by profile type
    attached_map: Dict[str, List[int]] = {}
    for entry in attached_list:
        attached_map.setdefault(entry['mdev'], []).append(entry['vmid'])

    # Build summary of vGPU types
    mdev_types: Dict[str, MdevProfile] = {}
    for prof in profiles:
        ptype = prof.get('type', '')
        available = bool(prof.get('available', prof.get('available_instances', 0)))
        profile: MdevProfile = {
            'name': prof.get('name', ''),
            'available': available,
            'description': prof.get('description', ''),
            'attached': ptype in attached_map
        }
        vmids = attached_map.get(ptype)
        if vmids:
            profile['attached_vmids'] = vmids  # type: ignore
        mdev_types[ptype] = profile

    return {'mdev_types': mdev_types}

@router.get("/available-gpus", response_model=AvailableGPUs)
async def get_available_gpus() -> AvailableGPUs:
    result: AvailableGPUs = {'mappings': {}}
    mappings = await _fetch_cluster_mappings()

    for mapping in mappings:
        if mapping.get('type') != 'pci':
            continue
        map_id = mapping['id']
        max_mdevs = mapping.get('mdev', 0)

        per_node: Dict[str, List[dict]] = {}
        for raw in mapping.get('map', []):
            parts = dict(item.split('=',1) for item in raw.split(',') if '=' in item)
            node = parts.get('node')
            path = parts.get('path')
            if node and path:
                per_node.setdefault(node, []).append({
                    'path': path,
                    'iommugroup': int(parts.get('iommugroup', 0)),
                    'subsystem_id': parts.get('subsystem-id', '')
                })

        mapping_info: MappingInfo = {'nodes': {}}
        for node, instances in per_node.items():
            mapping_info['nodes'][node] = await _process_node(node, instances, map_id, max_mdevs)

        result['mappings'][map_id] = mapping_info
    return result
