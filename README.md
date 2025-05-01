Create .env

PROXMOX_HOST=10.50.50.7:8006
PROXMOX_USER=root@pam
PROXMOX_TOKEN_NAME=token2
PROXMOX_TOKEN_VALUE=your-token
PROXMOX_VERIFY_SSL=false

Build 

docker build -t fastapi-gpu-api .

RUN
docker run -p 8000:8000 --env-file .env fastapi-gpu-api

Navigate to 127.0.0.0:8000/docs or http://127.0.0.1:8000/available-gpus