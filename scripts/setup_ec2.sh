#!/bin/bash

# ==============================================================================
# EC2 Instance Setup Script for Strava Club Activity Tracker
# ==============================================================================
#
# This script automates the setup of an Ubuntu EC2 instance for running the
# Strava Club Activity Tracker application with Docker Compose.
#
# Usage: Run this script on a fresh Ubuntu 22.04 EC2 instance
#   bash setup_ec2.sh
#

set -e  # Exit on error

echo "=================================================="
echo "Starting EC2 Setup for Strava Activity Tracker"
echo "=================================================="

# ------------------------------------------------------------------------------
# 1. Update system packages
# ------------------------------------------------------------------------------
echo ""
echo "[1/6] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# ------------------------------------------------------------------------------
# 2. Install Docker
# ------------------------------------------------------------------------------
echo ""
echo "[2/6] Installing Docker..."

# Install prerequisites
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

echo "Docker installed successfully!"
echo "Note: You may need to log out and back in for group membership to take effect."

# ------------------------------------------------------------------------------
# 3. Install Docker Compose (standalone)
# ------------------------------------------------------------------------------
echo ""
echo "[3/6] Installing Docker Compose..."

# Docker Compose v2 is already included with Docker CE, but install standalone for compatibility
DOCKER_COMPOSE_VERSION="v2.24.5"
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# ------------------------------------------------------------------------------
# 4. Enable Docker to start on boot
# ------------------------------------------------------------------------------
echo ""
echo "[4/6] Enabling Docker to start on boot..."
sudo systemctl enable docker
sudo systemctl start docker

# ------------------------------------------------------------------------------
# 5. Configure firewall (UFW)
# ------------------------------------------------------------------------------
echo ""
echo "[5/6] Configuring firewall..."

# Install UFW if not already installed
sudo apt-get install -y ufw

# Allow SSH (critical - do this first!)
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow FastAPI port (optional, for direct access)
sudo ufw allow 8000/tcp

# Enable firewall (with confirmation bypass for automation)
echo "y" | sudo ufw enable

# Show firewall status
sudo ufw status

# ------------------------------------------------------------------------------
# 6. Install additional useful tools
# ------------------------------------------------------------------------------
echo ""
echo "[6/6] Installing additional tools..."

sudo apt-get install -y \
    git \
    vim \
    htop \
    wget \
    unzip

# ------------------------------------------------------------------------------
# Setup complete
# ------------------------------------------------------------------------------
echo ""
echo "=================================================="
echo "EC2 Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Log out and back in to apply Docker group membership"
echo "  2. Clone your repository: git clone <your-repo-url>"
echo "  3. Create .env file from .env.example.production"
echo "  4. Run: docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "Verify installation:"
echo "  docker --version"
echo "  docker-compose --version"
echo "  docker ps"
echo ""
