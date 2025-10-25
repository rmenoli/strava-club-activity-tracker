# AWS EC2 Deployment Guide

This guide walks you through deploying the Strava Club Activity Tracker on a single AWS EC2 instance using Docker Compose.

## Table of Contents
- [Prerequisites](#prerequisites)
- [AWS Setup](#aws-setup)
- [EC2 Instance Setup](#ec2-instance-setup)
- [Application Deployment](#application-deployment)
- [Strava OAuth Configuration](#strava-oauth-configuration)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- AWS account with billing set up
- SSH client installed on your local machine
- Strava API application created at https://www.strava.com/settings/api
- Basic familiarity with terminal/command line

**Estimated monthly cost:** $18-25 (EC2 t3.small + storage)

---

## AWS Setup

### 1. Launch EC2 Instance

1. Log in to [AWS Console](https://console.aws.amazon.com/)
2. Navigate to **EC2** > **Launch Instance**
3. Configure instance:
   - **Name:** `strava-tracker`
   - **AMI:** Ubuntu Server 22.04 LTS (HVM), SSD Volume Type
   - **Instance type:** `t3.small` (2 vCPU, 2 GB RAM)
   - **Key pair:** Create new or select existing (download `.pem` file if new)
   - **Storage:** 20 GB gp3 SSD

### 2. Configure Security Group

Create a security group with the following inbound rules:

| Type  | Protocol | Port Range | Source      | Description         |
|-------|----------|------------|-------------|---------------------|
| SSH   | TCP      | 22         | Your IP     | SSH access          |
| HTTP  | TCP      | 80         | 0.0.0.0/0   | Web traffic         |
| Custom TCP | TCP  | 8000       | 0.0.0.0/0   | FastAPI (optional)  |

**Security Note:** For production, restrict SSH access to your IP only. Port 8000 is optional (used for direct access).

### 3. Allocate Elastic IP

1. In EC2 console, go to **Elastic IPs**
2. Click **Allocate Elastic IP address**
3. After allocation, click **Actions** > **Associate Elastic IP address**
4. Select your `strava-tracker` instance
5. Note down this IP address (needed for Strava OAuth)

### 4. SSH Key Permissions

On your local machine, set correct permissions for your SSH key:

```bash
chmod 400 ~/path/to/your-key.pem
```

---

## EC2 Instance Setup

### 1. Connect to Your Instance

```bash
ssh -i ~/path/to/your-key.pem ubuntu@YOUR_ELASTIC_IP
```

Replace `YOUR_ELASTIC_IP` with your allocated Elastic IP address.

### 2. Run Automated Setup Script

```bash
# Clone your repository
git clone https://github.com/yourusername/strava-club-activity-tracker.git
cd strava-club-activity-tracker

# Run setup script
bash scripts/setup_ec2.sh
```

This script will:
- Update system packages
- Install Docker and Docker Compose
- Configure firewall (UFW)
- Enable Docker to start on boot
- Install useful tools (git, vim, htop, etc.)

**Important:** After the script completes, **log out and back in** to apply Docker group membership:

```bash
exit  # Log out
ssh -i ~/path/to/your-key.pem ubuntu@YOUR_ELASTIC_IP  # Log back in
```

### 3. Verify Installation

```bash
docker --version
docker-compose --version
docker ps  # Should work without sudo
```

---

## Application Deployment

### 1. Configure Environment Variables

Create production `.env` file from template:

```bash
cd ~/strava-club-activity-tracker
cp .env.example.production .env
```

Edit the `.env` file:

```bash
vim .env  # or nano .env
```

Update these values:

```bash
# Database - change password from default
DATABASE_URL=postgresql://postgres:YOUR_SECURE_PASSWORD@postgres:5432/strava_tracker
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# Strava OAuth - from https://www.strava.com/settings/api
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REDIRECT_URI=http://YOUR_ELASTIC_IP/auth/strava/callback

# Security - generate with: openssl rand -hex 32
SECRET_KEY=your_secure_random_secret_key
```

**Generate secure SECRET_KEY:**
```bash
openssl rand -hex 32
```

### 2. Build and Start Services

```bash
# Build and start containers
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Check running containers
docker ps
```

You should see two containers running:
- `strava_tracker_db` (PostgreSQL)
- `strava_tracker_app` (FastAPI)

### 3. Verify Application

Test the application:

```bash
# From EC2 instance
curl http://localhost:8000

# From your browser
http://YOUR_ELASTIC_IP
```

You should see the welcome page.

---

## Strava OAuth Configuration

### Update Strava API Settings

1. Go to https://www.strava.com/settings/api
2. Update **Authorization Callback Domain** to: `YOUR_ELASTIC_IP`
3. Verify the redirect URI matches your `.env` file:
   ```
   http://YOUR_ELASTIC_IP/auth/strava/callback
   ```

### Test OAuth Flow

1. Visit `http://YOUR_ELASTIC_IP` in your browser
2. Click "Login with Strava"
3. Authorize the application
4. You should be redirected to your dashboard

---

## Maintenance

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f app
docker-compose -f docker-compose.prod.yml logs -f postgres
```

### Stop Services

```bash
docker-compose -f docker-compose.prod.yml down
```

### Restart Services

```bash
docker-compose -f docker-compose.prod.yml restart
```

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build
```

### Database Backup

**Manual backup:**
```bash
# Export database
docker exec strava_tracker_db pg_dump -U postgres strava_tracker > backup_$(date +%Y%m%d).sql

# Copy to local machine
scp -i ~/path/to/your-key.pem ubuntu@YOUR_ELASTIC_IP:~/strava-club-activity-tracker/backup_*.sql ./
```

**Restore from backup:**
```bash
# Copy backup to EC2
scp -i ~/path/to/your-key.pem backup_20250125.sql ubuntu@YOUR_ELASTIC_IP:~/

# Restore on EC2
docker exec -i strava_tracker_db psql -U postgres strava_tracker < backup_20250125.sql
```

**Automated backups (recommended):**
```bash
# Create backup script
cat > ~/backup.sh << 'SCRIPT'
#!/bin/bash
cd ~/strava-club-activity-tracker
docker exec strava_tracker_db pg_dump -U postgres strava_tracker | gzip > ~/backups/backup_$(date +%Y%m%d_%H%M%S).sql.gz
# Keep only last 7 days
find ~/backups -name "backup_*.sql.gz" -mtime +7 -delete
SCRIPT

chmod +x ~/backup.sh
mkdir -p ~/backups

# Add to crontab (daily at 2 AM)
echo "0 2 * * * ~/backup.sh" | crontab -
```

### Monitor Resources

```bash
# Disk usage
df -h

# Docker disk usage
docker system df

# Container stats (CPU, memory)
docker stats

# System resources
htop
```

---

## Troubleshooting

### Application Not Accessible

**Check if containers are running:**
```bash
docker ps
```

**Check logs for errors:**
```bash
docker-compose -f docker-compose.prod.yml logs app
docker-compose -f docker-compose.prod.yml logs postgres
```

**Verify firewall rules:**
```bash
sudo ufw status
```

**Test local connectivity:**
```bash
curl http://localhost:8000
```

### Database Connection Issues

**Check database container:**
```bash
docker-compose -f docker-compose.prod.yml logs postgres
```

**Verify DATABASE_URL in .env:**
```bash
# Should use 'postgres' as hostname (Docker service name)
DATABASE_URL=postgresql://postgres:password@postgres:5432/strava_tracker
```

**Test database connection:**
```bash
docker exec -it strava_tracker_db psql -U postgres strava_tracker
```

### Strava OAuth Errors

**Common issues:**
1. **Redirect URI mismatch:** Ensure `.env` matches Strava API settings exactly
2. **Application not authorized:** Check Strava API application status
3. **Invalid credentials:** Verify `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`

**Check application logs:**
```bash
docker-compose -f docker-compose.prod.yml logs app | grep -i "strava\|oauth\|auth"
```

### Out of Disk Space

**Clean Docker resources:**
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (WARNING: removes data)
docker volume prune

# Remove all unused resources
docker system prune -a --volumes
```

### High Memory Usage

**Check container memory usage:**
```bash
docker stats --no-stream
```

**Restart services to free memory:**
```bash
docker-compose -f docker-compose.prod.yml restart
```

### Rebuild After Code Changes

```bash
# Rebuild and restart (no cache)
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

---

## Upgrading to Production Architecture

When you're ready to scale, consider:

1. **Add Domain + HTTPS:**
   - Register domain (Route 53, Namecheap, etc.)
   - Add Application Load Balancer
   - Use AWS Certificate Manager for free SSL

2. **Migrate to RDS:**
   - Create RDS PostgreSQL instance
   - Export data from Docker container
   - Import to RDS
   - Update `DATABASE_URL` in `.env`

3. **Move to ECS:**
   - Create ECS cluster
   - Push Docker image to ECR
   - Create task definition
   - Set up auto-scaling

4. **Add Monitoring:**
   - CloudWatch Logs
   - CloudWatch Alarms (CPU, memory, disk)
   - Application Performance Monitoring (APM)

---

## Cost Optimization Tips

1. **Use Reserved Instances:** Save 30-40% with 1-year commitment
2. **Schedule instance:** Stop during off-hours if not needed 24/7
3. **Monitor data transfer:** Minimize data egress costs
4. **Right-size instance:** Start with t3.small, scale as needed

---

## Support

For issues or questions:
- Application issues: Check logs and troubleshooting section above
- AWS issues: https://aws.amazon.com/support/
- Strava API issues: https://developers.strava.com/

---

**Last updated:** 2025-01-25
