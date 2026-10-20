#!/bin/bash

# Fly.io Secrets Configuration Script
# Sets up all required secrets for Binomial Risk Analyst V6
# Usage: ./scripts/setup_fly_secrets.sh

echo "Setting up Fly.io secrets for Binomial Risk Analyst V6..."

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Error: fly CLI is not installed. Install it from https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Check if logged in to Fly
if ! fly auth whoami &> /dev/null; then
    echo "Error: Not logged in to Fly. Run 'fly auth login' first."
    exit 1
fi

APP_NAME="binomial-sentry"

echo "Setting secrets for app: $APP_NAME"

# Core API Keys
fly secrets set OPENAI_API_KEY="your_openai_api_key_here" -a $APP_NAME
fly secrets set PERPLEXITY_API_KEY="your_perplexity_api_key_here" -a $APP_NAME
fly secrets set FRED_API_KEY="your_fred_api_key_here" -a $APP_NAME

# Clerk Authentication (Aug 2025 standard)
fly secrets set CLERK_SECRET_KEY="your_clerk_secret_key_here" -a $APP_NAME
fly secrets set CLERK_WEBHOOK_SECRET="your_clerk_webhook_secret_here" -a $APP_NAME
fly secrets set CLERK_INSTANCE_URL="https://your-instance.clerk.accounts.dev" -a $APP_NAME

# PostgreSQL Connection (Fly Postgres or external)
# For Fly Postgres, use: fly postgres attach --app $APP_NAME
# This will automatically set DATABASE_URL
# For external PostgreSQL:
# fly secrets set DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require" -a $APP_NAME

# Redis Configuration (optional)
# fly secrets set REDIS_URL="redis://default:password@host:6379" -a $APP_NAME

# Risk Analysis Settings
fly secrets set PORTFOLIO_VALUE="1000000" -a $APP_NAME
fly secrets set MC_SIMULATIONS="1000" -a $APP_NAME
fly secrets set MC_TIME_HORIZON="252" -a $APP_NAME

# Optional: Groq and HuggingFace for LangGraph routing
fly secrets set GROQ_API_KEY="your_groq_api_key_here" -a $APP_NAME
fly secrets set HF_TOKEN="your_huggingface_token_here" -a $APP_NAME

echo ""
echo "Secrets configuration complete!"
echo ""
echo "Next steps:"
echo "1. Edit this script with your actual API keys"
echo "2. Run: chmod +x scripts/setup_fly_secrets.sh"
echo "3. Run: ./scripts/setup_fly_secrets.sh"
echo "4. Attach PostgreSQL: fly postgres attach --app $APP_NAME"
echo "5. Deploy: fly deploy"
echo ""
echo "To verify secrets: fly secrets list -a $APP_NAME"