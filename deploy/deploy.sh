#!/bin/bash
set -e

SERVER="root@your-server-ip"
DEPLOY_PATH="/home/pindou"

echo "=== 1. Build frontend ==="
cd "$(dirname "$0")/../frontend-vue"
npm run build

echo "=== 2. Upload files ==="
ssh $SERVER "mkdir -p $DEPLOY_PATH/backend $DEPLOY_PATH/frontend-vue/dist"

# Upload backend
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'venv' \
    --exclude 'uploads' \
    --exclude 'card_state.json' \
    ../backend/ \
    $SERVER:$DEPLOY_PATH/backend/

# Upload frontend build
rsync -avz --delete \
    dist/ \
    $SERVER:$DEPLOY_PATH/frontend-vue/dist/

echo "=== 3. Setup backend on server ==="
ssh $SERVER "cd $DEPLOY_PATH/backend && \
    python3 -m venv venv && \
    venv/bin/pip install -r requirements.txt"

echo "=== 4. Setup nginx ==="
scp nginx.conf $SERVER:/etc/nginx/sites-available/pindou.conf
ssh $SERVER "rm -f /etc/nginx/sites-enabled/default && \
    ln -sf /etc/nginx/sites-available/pindou.conf /etc/nginx/sites-enabled/ && \
    nginx -t && systemctl reload nginx"

echo "=== 5. Setup systemd service ==="
scp pindou-backend.service $SERVER:/etc/systemd/system/
ssh $SERVER "systemctl daemon-reload && \
    systemctl enable pindou-backend && \
    systemctl restart pindou-backend"

echo "=== Deploy complete! ==="
