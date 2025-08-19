#!/bin/bash

# This script prepares a Google Colab environment to run the project.
# It installs system dependencies, Google Chrome, the correct ChromeDriver,
# and all necessary Python packages.

echo "--- Preparing Google Colab Environment ---"

# 1. Install system dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y wget curl unzip

# 2. Install Google Chrome
echo "[2/5] Installing Google Chrome..."
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
# Fix any dependency issues that might have occurred
sudo apt-get install -f -y
rm google-chrome-stable_current_amd64.deb

# 3. Install ChromeDriver
# Note: This will install the chromedriver for the stable version of Chrome installed above.
echo "[3/5] Installing ChromeDriver..."
CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE_$(google-chrome --version | cut -d' ' -f3 | cut -d'.' -f1))
wget -q https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
rm chromedriver_linux64.zip

# 4. Install Python packages
echo "[4/5] Installing Python packages from requirements.txt..."
pip install -r requirements.txt

# 5. Final check
echo "[5/5] Setup complete. Environment should be ready."
google-chrome --version
chromedriver --version
