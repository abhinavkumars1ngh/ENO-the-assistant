#!/bin/bash

# Build script for ENO local package

PACKAGE_NAME="eno-local-installer"
DIST_DIR="dist/$PACKAGE_NAME"
TARBALL="dist/${PACKAGE_NAME}.tar.gz"

# Check idempotency
if [ "$1" != "--force" ] && [ -f "$TARBALL" ]; then
    # Find the newest file in the source directories
    NEWEST_FILE=$(find backend frontend requirements.txt start_project.py -type f -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -not -name ".DS_Store" -exec stat -f "%m" {} + | sort -n | tail -1)
    TARBALL_TIME=$(stat -f "%m" "$TARBALL")
    
    if [ "$NEWEST_FILE" -le "$TARBALL_TIME" ]; then
        echo "[Eno Builder] Package is up to date, nothing to rebuild. Run with --force to rebuild anyway."
        exit 0
    fi
    echo "[Eno Builder] Source files changed. Rebuilding..."
fi

echo "[Eno Builder] Starting build process..."
rm -rf dist/
mkdir -p "$DIST_DIR"

echo "[Eno Builder] Generating .env.example..."
cat << 'ENV_EOF' > "$DIST_DIR/.env.example"
# ==========================================
# ENO AI Local Configuration
# Rename this file to .env and fill it out
# ==========================================

# (Required) Your Google OAuth Client ID for frontend login
GOOGLE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"

# (Required) Your Google OAuth Client Secret
GOOGLE_CLIENT_SECRET="your-google-client-secret"

# (Required) JWT Secret for backend session signing (generate a random string)
JWT_SECRET="your-random-jwt-secret-string"

# (Optional) Hugging Face token if your model repo is private/gated
# HF_TOKEN="hf_..."
ENV_EOF

echo "[Eno Builder] Copying backend..."
cp -r backend "$DIST_DIR/"
cp requirements.txt "$DIST_DIR/"

echo "[Eno Builder] Building and copying frontend..."
cd frontend
npm ci
npm run build
cd ..
cp -r frontend "$DIST_DIR/"

echo "[Eno Builder] Copying orchestration scripts..."
cp start_project.py "$DIST_DIR/"
cp autoeck.py "$DIST_DIR/"
cp package.json "$DIST_DIR/" 2>/dev/null || true

# Setup script for the user
cat << 'SETUP_EOF' > "$DIST_DIR/setup.sh"
#!/bin/bash
echo "[Eno Setup] Welcome to ENO AI!"

# 1. Cloudflared check
if ! command -v cloudflared &> /dev/null; then
    echo "[Eno Setup] 'cloudflared' is not installed."
    echo "[Eno Setup] Please install it by running: brew install cloudflare/cloudflare/cloudflared"
    echo "[Eno Setup] After installing, re-run this setup script."
    exit 1
fi

# 2. Python Virtual Environment and pip dependencies
if [ -d "venv312" ]; then
    echo "[Eno Setup] Virtual environment 'venv312' already exists. Checking dependencies..."
    source venv312/bin/activate
    # A simple check: if requirements.txt is newer than the venv directory, reinstall
    if [ requirements.txt -nt venv312 ]; then
        echo "[Eno Setup] requirements.txt has changed. Updating Python dependencies..."
        pip install --upgrade pip
        pip install -r requirements.txt
        touch venv312 # Update venv timestamp
    else
        echo "[Eno Setup] Python dependencies are already up to date."
    fi
else
    echo "[Eno Setup] Creating Python virtual environment..."
    python3 -m venv venv312
    source venv312/bin/activate
    echo "[Eno Setup] Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# 3. Frontend dependencies
echo "[Eno Setup] Checking frontend dependencies..."
cd frontend
if [ -d "node_modules" ] && [ package-lock.json -ot node_modules ]; then
    echo "[Eno Setup] Frontend dependencies already up to date."
else
    echo "[Eno Setup] Installing frontend dependencies (npm ci)..."
    npm ci
    touch node_modules # Update node_modules timestamp
fi
cd ..

if [ ! -f ".env" ]; then
    echo "[Eno Setup] WARNING: No .env file found. Please copy .env.example to .env and fill it out!"
fi

echo "[Eno Setup] Dependencies installed. You can now run: python start_project.py"
SETUP_EOF
chmod +x "$DIST_DIR/setup.sh"

echo "[Eno Builder] Compressing package (ignoring model weights and large storage)..."
cd dist
tar -czvf "${PACKAGE_NAME}.tar.gz" \
    --exclude="frontend/node_modules" \
    --exclude="backend/__pycache__" \
    --exclude=".env" \
    "$PACKAGE_NAME"

echo "[Eno Builder] Build complete! Package is at dist/${PACKAGE_NAME}.tar.gz"
