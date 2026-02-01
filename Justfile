# Justfile for arxivbot deployment

# Run locally
dev:
    uv run uvicorn arxivbot.main:app --reload

# Check health locally before deploy
check:
    @curl -sf http://localhost:8000/health | grep -q "ok" && echo "Health OK" || echo "Health check failed"

# First-time setup (run once)
provision region="sjc":
    fly launch --no-deploy --name arxivbot --region {{region}}
    fly volumes create arxivbot_data --size 1 --region {{region}}
    @echo "Now run: fly secrets set GEMINI_API_KEY=your-key"

# Deploy to Fly.io
deploy:
    fly deploy
    @just verify

# Verify deployment succeeded
verify:
    @echo "Checking deployment status..."
    fly status
    @sleep 5
    @curl -sf https://arxivbot.fly.dev/health && echo "Deploy successful!" || echo "Health check failed"

# View logs
logs:
    fly logs

# SSH into running instance
ssh:
    fly ssh console

# Setup custom domain
domain:
    fly certs create arxivbot.org
    fly certs create www.arxivbot.org
    @echo "Add DNS records at Porkbun:"
    fly certs show arxivbot.org

# Check domain status
domain-check:
    fly certs check arxivbot.org
