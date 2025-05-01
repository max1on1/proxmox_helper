from proxmoxer import ProxmoxAPI
import config

proxmox = ProxmoxAPI(
    config.PROXMOX_HOST,
    user=config.PROXMOX_USER,
    token_name=config.PROXMOX_TOKEN_NAME,
    token_value=config.PROXMOX_TOKEN_VALUE,
    verify_ssl=config.PROXMOX_VERIFY_SSL
)