# DocRebuild AI — Docker GPU Deployment Guide

This guide describes the complete process of deploying **DocRebuild AI** using Docker and Docker Compose on an Ubuntu GPU server (like DigitalOcean H200/A10G with the "AI/ML Ready" image).

---

## 1. Install Docker & NVIDIA Container Toolkit

To run GPU workloads inside Docker containers, the host server must have the NVIDIA Container Toolkit installed, allowing GPU pass-through.

### Step 1: Install Docker and Docker Compose
Use the official Docker convenience script to install Docker CE and the Docker Compose plugin safely on Ubuntu:
```bash
# Download the installer script
curl -fsSL https://get.docker.com -o get-docker.sh

# Run the installer
sudo sh get-docker.sh

# Add your user to the docker group (optional, to run docker without sudo)
sudo usermod -aG docker $USER
```
After executing this, log out and log back in, or run `newgrp docker` to apply the group changes.

### Step 2: Install NVIDIA Container Toolkit
Add the GPG key and repository list, install the toolkit, and restart Docker:
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker daemon to use the NVIDIA runtime
sudo nvidia-container-toolkit-config --mode=docker
sudo systemctl restart docker
```

Verify that Docker can access the GPU:
```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
# This should print the H200 GPU details (141 GB VRAM, Driver Version, CUDA Version)
```

---

## 2. Clone & Environment Configuration

### Step 1: Clone the Code
```bash
git clone https://github.com/mahedi-emon/DocRebuild-AI.git
cd DocRebuild-AI
```

### Step 2: Set Environment Config
Create the `.env` configuration file:
```bash
cp .env.example .env
```
Ensure the `.env` contains the H200-optimized GPU configuration:
```env
APP_ENV=production
DEBUG=false
DEVICE=cuda
GPU_MEMORY_LIMIT_MB=141000
WORKERS=4

# Enabled models
ENABLE_SURYA=true
ENABLE_PADDLEOCR=true
ENABLE_TESSERACT=true
ENABLE_EASYOCR=true
ENABLE_TROCR=true
ENABLE_DOCTR=true
ENABLE_DOCLAYOUT_YOLO=true
ENABLE_DOCLING=true
ENABLE_MARKER=true
ENABLE_FLORENCE2=true
ENABLE_QWEN_VL=true
ENABLE_INTERNVL=true
```

---

## 3. Run the Docker Stack

### Step 1: Build the Containers
Build the React frontend and CUDA backend images:
```bash
docker compose build
```
*(This downloads model base layers and installs Python dependencies, taking about 3-5 minutes on the first run).*

### Step 2: Start the Containers
Start the backend and frontend services in daemon mode:
```bash
docker compose up -d
```

### Step 3: Verify the Running Containers
```bash
docker compose ps
```
You should see:
- `backend` running on port `8000`
- `frontend` running on port `3000`

---

## 4. Reverse Proxy & SSL (Domain Setup)

Since Nginx inside the frontend container runs on port `80` (mapped to port `3000` on the host), we will set up Nginx on the host server to proxy request to port `3000` and handle Let's Encrypt SSL.

### Step 1: Install Host Nginx
```bash
sudo apt-get install -y nginx
```

### Step 2: Create Server Block
```bash
sudo nano /etc/nginx/sites-available/docrebuild
```
Paste the following reverse-proxy configuration:
```nginx
server {
    listen 80;
    server_name docrebuild.mahedihasanemon.site;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        client_max_body_size 500M;
    }
}
```

Enable the configuration and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/docrebuild /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default 2>/dev/null
sudo nginx -t
sudo systemctl restart nginx
```

### Step 3: Secure with SSL (Certbot)
Obtain a free SSL certificate from Let's Encrypt:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d docrebuild.mahedihasanemon.site
```
Choose the redirection option to force all traffic through HTTPS.

---

## 5. Maintenance & Logs

* **View Logs in Real-time:**
  ```bash
  docker compose logs -f
  ```
* **Restart the Stack:**
  ```bash
  docker compose restart
  ```
* **Stop the Stack:**
  ```bash
  docker compose down
  ```
* **Cleanup Unused Docker Data (to reclaim disk space):**
  ```bash
  docker system prune -af --volumes
  ```
