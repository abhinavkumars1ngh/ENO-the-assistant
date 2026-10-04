#!/bin/bash

# Build script for ENO local package

echo "[Eno Builder] Starting build process..."
PACKAGE_NAME="eno-local-installer"
DIST_DIR="dist/$PACKAGE_NAME"

# Clean previous build
rm -rf dist/
mkdir -p "$DIST_DIR"

echo "[Eno Builder] Copying backend..."
cp -r backend "$DIST_DIR/"
cp requirements.txt "$DIST_DIR/"

echo "[Eno Builder] Building and copying frontend..."
cd frontend
npm ci
npm run build
# We'll copy the whole frontend for now (since start_project uses npm run dev). 
# If a static export is preferred in the future, we can run `npm run export` and serve via FastAPI.
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
echo "[Eno Setup] Creating Python virtual environment..."
python3 -m venv venv312
source venv312/bin/activate
echo "[Eno Setup] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
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
