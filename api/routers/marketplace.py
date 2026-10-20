from fastapi import APIRouter, HTTPException, Request
from typing import List
from api.models_dir.marketplace import MarketplaceResponse, Integration, IntegrationCategory, IntegrationStatus
from core.database.postgres_client import get_postgres_rls_client

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

# Integration definitions
INTEGRATIONS = [
    # Cloud Storage
    Integration(
        id="google_drive",
        name="Google Drive",
        description="Access and analyze files from Google Drive.",
        category=IntegrationCategory.CLOUD,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/connector-logos/google-drive.png",
        long_description="Google Drive integration allows you to seamlessly access your documents, spreadsheets, and presentations directly within the platform. Analyze content, extract insights, and incorporate file data into your workflows.",
        features=[
            "Access Google Docs, Sheets, and Slides",
            "Search files by name or content",
            "Analyze file contents with AI",
            "Secure OAuth2 authentication"
        ],
        supported_file_types=["docx", "xlsx", "pptx", "pdf", "txt", "csv"]
    ),
    Integration(
        id="onedrive_business",
        name="OneDrive Business",
        description="Access files from OneDrive for Business accounts.",
        category=IntegrationCategory.CLOUD,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/connector-logos/one-drive.png",
        long_description="Connect your OneDrive for Business account to bring enterprise documents into your analysis workflows. Securely access files stored in your organization's cloud storage.",
        features=[
            "Enterprise-grade security",
            "Access shared libraries",
            "Sync changes automatically",
            "Support for large files"
        ]
    ),
    Integration(
        id="onedrive_personal",
        name="OneDrive Personal",
        description="Access files from personal OneDrive accounts.",
        category=IntegrationCategory.CLOUD,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/connector-logos/one-drive.png",
        long_description="Link your personal OneDrive to easily access your private files and documents. Perfect for individual users needing to analyze personal data.",
        features=[
            "Easy setup",
            "Access personal folders",
            "View and analyze photos and documents"
        ]
    ),
    Integration(
        id="sharepoint",
        name="SharePoint",
        description="Connect to SharePoint document libraries.",
        category=IntegrationCategory.CLOUD,
        status=IntegrationStatus.DISCONNECTED, # Default to disconnected, updated dynamically
        icon_url="/connector-logos/sharepoint-logo.png",
        long_description="SharePoint integration enables access to team sites and document libraries. Collaborate effectively by bringing team knowledge into your analytical workspace.",
        features=[
            "Access Team Sites",
            "Document Library support",
            "Permission-aware access",
            "Metadata extraction"
        ]
    ),
    Integration(
        id="aws",
        name="AWS S3",
        description="Access files stored in Amazon S3 buckets.",
        category=IntegrationCategory.CLOUD,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/aws.png",
        long_description="Connect to your AWS S3 buckets to analyze large datasets and documents securely stored in the cloud.",
        features=[
            "S3 Bucket access",
            "Secure IAM authentication",
            "Large file support"
        ]
    ),
    Integration(
        id="google_cloud",
        name="Google Cloud Storage",
        description="Access files stored in Google Cloud Storage.",
        category=IntegrationCategory.CLOUD,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/google-cloud.png",
        long_description="Integrate with Google Cloud Storage to bring your cloud assets into your analytical workflows.",
        features=[
            "GCS Bucket access",
            "Service Account authentication",
            "Enterprise scale"
        ]
    ),
    
    # Database Services
    Integration(
        id="postgres",
        name="PostgreSQL",
        description="Connect to external PostgreSQL databases.",
        category=IntegrationCategory.DATABASE,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/postgres.svg" 
    ),
    Integration(
        id="snowflake",
        name="Snowflake",
        description="Analyze data stored in Snowflake data warehouses.",
        category=IntegrationCategory.DATABASE,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/snowflake.png"
    ),
    Integration(
        id="databricks",
        name="Databricks",
        description="Integrate Databricks for data engineering, ML, and data science.",
        category=IntegrationCategory.DATABASE,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/databricks.png"
    ),
    Integration(
        id="oracle",
        name="Oracle Database",
        description="Connect to Oracle Database and OCI services.",
        category=IntegrationCategory.DATABASE,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/oracle.png",
        long_description="Integrate with Oracle Database to access enterprise-grade relational data. Supports connection to both on-premise and OCI-hosted instances.",
        features=[
            "Oracle SQL support",
            "Secure connection tunneling",
            "Large dataset handling"
        ]
    ),

    # LLMs
    Integration(
        id="gpt-5.4-thinking",
        name="GPT-5.4 Thinking",
        description="OpenAI's best model for complex analysis and reasoning.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/gpt-logo.png",
        long_description="Connect your own OpenAI API key to access GPT-5.4 Thinking. This model excels at complex analysis, reasoning tasks, and deep dives into financial data.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Enhanced reasoning capabilities",
            "300K token context window",
            "Secure API key storage"
        ],
        setup_guide_url="https://platform.openai.com/api-keys"
    ),
    Integration(
        id="gpt-5.4",
        name="GPT-5.4",
        description="Latest GPT-5.4 with enhanced reasoning capabilities.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/gpt-logo.png",
        long_description="Connect your own OpenAI API key to access GPT-5.4. Features the latest reasoning enhancements for superior performance.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Latest reasoning engine",
            "300K token context window",
            "Superior complex task handling"
        ],
        setup_guide_url="https://platform.openai.com/api-keys"
    ),
    Integration(
        id="gpt-5.1",
        name="GPT-5.1",
        description="Quick responses for everyday tasks from OpenAI.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/gpt-logo.png",
        long_description="Connect your OpenAI API key to use GPT-5.1. Perfect for everyday tasks requiring speed and efficiency without sacrificing too much intelligence.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Fast response times",
            "Cost-effective",
            "300K token context window"
        ],
        setup_guide_url="https://platform.openai.com/api-keys"
    ),
    Integration(
        id="claude-opus",
        name="Claude 4.5 Opus",
        description="Anthropic's highest capability model for nuanced tasks.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/claude-logo.svg.png",
        long_description="Connect your Anthropic API key to access Claude 4.5 Opus. Ideal for tasks requiring high nuance, complex writing, and deep understanding.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Highest capability model",
            "150K token context window",
            "Excellent for long-form content"
        ],
        setup_guide_url="https://console.anthropic.com/settings/keys"
    ),
    Integration(
        id="claude-sonnet",
        name="Claude 4.5 Sonnet",
        description="Great balance of speed and intelligence from Anthropic.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/claude-logo.svg.png",
        long_description="Connect your Anthropic API key to use Claude 4.5 Sonnet. The versatile choice for most professional workflows.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Balanced performance",
            "150K token context window",
            "Reliable reasoning"
        ],
        setup_guide_url="https://console.anthropic.com/settings/keys"
    ),
    Integration(
        id="claude-haiku",
        name="Claude 4.5 Haiku",
        description="Quick responses with good accuracy from Anthropic.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/claude-logo.svg.png",
        long_description="Connect your Anthropic API key to use Claude 4.5 Haiku. Fast and efficient for high-volume tasks.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Fastest Claude model",
            "150K token context window",
            "Cost-effective"
        ],
        setup_guide_url="https://console.anthropic.com/settings/keys"
    ),
    Integration(
        id="gemini-pro",
        name="Gemini 3 Pro",
        description="Google's high-depth reasoning model with multimodal support.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/gemini-logo.png",
        long_description="Connect your Google AI Studio key to access Gemini 3 Pro. Features massive context windows and native multimodal capabilities.",
        features=[
            "Bring Your Own Key (BYOK)",
            "750K token context window",
            "Multimodal understanding",
            "Google ecosystem integration"
        ],
        setup_guide_url="https://aistudio.google.com/app/apikey"
    ),
    Integration(
        id="gemini-flash-lite",
        name="Gemini 2.5 Flash Lite",
        description="Ultra-low latency legacy Gemini variant optimized for quick responses.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/gemini-logo.png",
        long_description="Connect your Google AI Studio key to access Gemini 2.5 Flash Lite. Optimized for speed and efficiency.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Ultra-low latency",
            "750K token context window",
            "Efficient processing"
        ],
        setup_guide_url="https://aistudio.google.com/app/apikey"
    ),
    Integration(
        id="deepseek-chat",
        name="DeepSeek 3.2 Chat",
        description="DeepSeek Chat (3.2) tuned for broad financial analysis.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/deepseek.png",
        long_description="Connect your DeepSeek API key to use DeepSeek 3.2 Chat. Tuned for financial analysis and general tasks.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Financial analysis tuning",
            "75K token context window",
            "Broad knowledge base"
        ],
        setup_guide_url="https://platform.deepseek.com/api_keys"
    ),
    Integration(
        id="deepseek-reasoner",
        name="DeepSeek R1 Reasoner",
        description="DeepSeek reasoner with extended chain-of-thought support.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/deepseek.png",
        long_description="Connect your DeepSeek API key to use the R1 Reasoner. Optimized for solving difficult problems through extended chain-of-thought.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Chain-of-thought reasoning",
            "75K token context window",
            "Strong code generation"
        ],
        setup_guide_url="https://platform.deepseek.com/api_keys"
    ),
    Integration(
        id="grok-reasoning",
        name="Grok 4.1 Reasoning",
        description="xAI's accelerated model with reasoning traces.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/grok.png",
        long_description="Connect your xAI API key to access Grok 4.1 Reasoning. Provides transparent reasoning traces for complex analytical tasks.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Reasoning traces",
            "1M token context window",
            "Real-time knowledge access"
        ],
        setup_guide_url="https://console.x.ai/"
    ),
    Integration(
        id="grok-fast",
        name="Grok 4.1 Fast",
        description="High-speed Grok 4.1 responses without reasoning traces.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/grok.png",
        long_description="Connect your xAI API key to access Grok 4.1 Fast. High-speed responses for quick interactions.",
        features=[
            "Bring Your Own Key (BYOK)",
            "High-speed responses",
            "1M token context window",
            "Efficient processing"
        ],
        setup_guide_url="https://console.x.ai/"
    ),
    Integration(
        id="llama-scout",
        name="Llama 4 Scout",
        description="Meta Llama 4 Scout on AWS Bedrock.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/assets/model-logos/meta-logo.png",
        long_description="Coming soon: Meta Llama 4 Scout accessed via AWS Bedrock.",
        features=[
            "Coming Soon",
            "3.2M token context window",
            "AWS Bedrock integration"
        ]
    ),
    Integration(
        id="perplexity",
        name="Perplexity Sonar Pro",
        description="Premium web search with citations and analysis.",
        category=IntegrationCategory.LLM,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/assets/model-logos/perplexity-logo.png",
        long_description="Connect your Perplexity API key for real-time web search capabilities grounded with citations.",
        features=[
            "Bring Your Own Key (BYOK)",
            "Real-time web search",
            "Citations included",
            "Up-to-date information"
        ],
        setup_guide_url="https://www.perplexity.ai/settings/api"
    ),


    # Communicators
    Integration(
        id="slack",
        name="Slack",
        description="Interact via Slack channels and direct messages.",
        category=IntegrationCategory.COMMUNICATOR,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/connector-logos/slack-logo.png"
    ),
    Integration(
        id="teams",
        name="Microsoft Teams",
        description="Interact via Microsoft Teams chats.",
        category=IntegrationCategory.COMMUNICATOR,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/connector-logos/teams-logo.png"
    ),
    Integration(
        id="email",
        name="Email",
        description="Send and receive emails.",
        category=IntegrationCategory.COMMUNICATOR,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/email-icon.png"
    ),


    # Actions
    Integration(
        id="zapier",
        name="Zapier",
        description="Trigger automated workflows in thousands of apps.",
        category=IntegrationCategory.ACTION,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/icons/zapier.svg"
    ),
    Integration(
        id="sendgrid",
        name="SendGrid",
        description="Send automated emails and reports.",
        category=IntegrationCategory.ACTION,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/icons/sendgrid.svg"
    ),
    
    # Brokerage
    Integration(
        id="ibkr",
        name="Interactive Brokers",
        description="Sync portfolio and trading data from IBKR.",
        category=IntegrationCategory.BROKERAGE,
        status=IntegrationStatus.DISCONNECTED,
        icon_url="/connector-logos/ibkr-logo.png",
        long_description="Connect your Interactive Brokers account using Flex Query credentials to automatically sync your portfolio positions, cash balances, and trade history.",
        features=[
            "Automatic portfolio sync",
            "Real-time position tracking",
            "Cash balance & multi-currency support",
            "Trade history import",
            "Secure Flex Token authentication"
        ],
        setup_guide_url="https://www.interactivebrokers.com/en/software/am/am/reports/flexqueries.htm"
    ),
    Integration(
        id="robinhood",
        name="Robinhood",
        description="Trade and view portfolio with Robinhood.",
        category=IntegrationCategory.BROKERAGE,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/robinhood-logo.png"
    ),
    Integration(
        id="schwab",
        name="Charles Schwab",
        description="Trade and view portfolio with Schwab.",
        category=IntegrationCategory.BROKERAGE,
        status=IntegrationStatus.COMING_SOON,
        icon_url="/connector-logos/schwab-logo.png"
    ),
]

@router.get("/list", response_model=MarketplaceResponse)
async def list_integrations(request: Request):
    """
    Get a list of all available marketplace integrations.
    Checks connection status for cloud storage, communication, and brokerage integrations.
    """
    user_id = getattr(request.state, "user_id", None)
    org_id = getattr(request.state, "org_id", None) or ""
    
    # Clone the static list to avoid modifying it globally
    response_integrations = [i.copy() for i in INTEGRATIONS]
    
    # Check connection status if user is authenticated
    google_drive_connected = False
    onedrive_connected = False
    sharepoint_connected = False
    slack_connected = False
    teams_connected = False
    ibkr_connected = False
    
    if user_id:
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                # Check Google Drive
                google_drive_connected = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM google_drive_credentials WHERE user_id = $1)",
                    user_id
                )
                # Check OneDrive
                onedrive_connected = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM onedrive_credentials WHERE user_id = $1)",
                    user_id
                )
                
                # Check SharePoint - Mirror OneDrive status
                sharepoint_connected = onedrive_connected
                
                # Check Slack
                try:
                    slack_connected = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM slack_credentials WHERE user_id = $1)",
                        user_id
                    )
                except Exception:
                    pass
                
                # Check Teams
                try:
                    teams_connected = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM teams_credentials WHERE user_id = $1)",
                        user_id
                    )
                except Exception:
                    pass
                
            # Check IBKR with org context
            async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
                try:
                    ibkr_connected = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM broker_connections WHERE user_id = $1 AND broker_type = 'ibkr' AND status = 'active' AND org_id = $2)",
                        user_id, org_id
                    )
                except Exception:
                    pass
                
        except Exception:
            pass

    # Update statuses
    for integration in response_integrations:
        if integration.id == "google_drive":
            integration.status = IntegrationStatus.CONNECTED if google_drive_connected else IntegrationStatus.DISCONNECTED
        elif integration.id in ["onedrive_business", "onedrive_personal"]:
            integration.status = IntegrationStatus.CONNECTED if onedrive_connected else IntegrationStatus.DISCONNECTED
        elif integration.id == "sharepoint":
            integration.status = IntegrationStatus.CONNECTED if sharepoint_connected else IntegrationStatus.DISCONNECTED
        elif integration.id == "slack":
            integration.status = IntegrationStatus.CONNECTED if slack_connected else IntegrationStatus.DISCONNECTED
        elif integration.id == "teams":
            integration.status = IntegrationStatus.CONNECTED if teams_connected else IntegrationStatus.DISCONNECTED
        elif integration.id == "ibkr":
            integration.status = IntegrationStatus.CONNECTED if ibkr_connected else IntegrationStatus.DISCONNECTED
        elif integration.category == IntegrationCategory.LLM:
            # All LLMs are platform-provided, mark as connected
            integration.status = IntegrationStatus.CONNECTED
    
    return MarketplaceResponse(integrations=response_integrations)

@router.get("/{integration_id}", response_model=Integration)
async def get_integration_details(integration_id: str, request: Request):
    """
    Get details for a specific integration.
    """
    # Find integration in static list
    integration = next((i for i in INTEGRATIONS if i.id == integration_id), None)
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    # Clone to update status
    response_integration = integration.copy()
    
    user_id = getattr(request.state, "user_id", None)
    org_id = getattr(request.state, "org_id", None) or ""
    
    if user_id:
        try:
            pg = await get_postgres_rls_client()
            connected = False
            
            async with pg.acquire_with_user_context(user_id) as conn:
                if integration_id == "google_drive":
                    connected = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM google_drive_credentials WHERE user_id = $1)", user_id)
                elif integration_id in ["onedrive_business", "onedrive_personal"]:
                    connected = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM onedrive_credentials WHERE user_id = $1)", user_id)
                elif integration_id == "sharepoint":
                    connected = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM onedrive_credentials WHERE user_id = $1)", user_id)
                elif integration_id == "slack":
                    try:
                        connected = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM slack_credentials WHERE user_id = $1)", user_id)
                    except Exception:
                        pass
                elif integration_id == "teams":
                    try:
                        connected = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM teams_credentials WHERE user_id = $1)", user_id)
                    except Exception:
                        pass
            
            # Check IBKR with org context
            if integration_id == "ibkr":
                async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
                    try:
                        connected = await conn.fetchval(
                            "SELECT EXISTS(SELECT 1 FROM broker_connections WHERE user_id = $1 AND broker_type = 'ibkr' AND status = 'active' AND org_id = $2)",
                            user_id, org_id
                        )
                    except Exception:
                        pass
                
            if connected:
                response_integration.status = IntegrationStatus.CONNECTED
                    
        except Exception:
            pass
            
    return response_integration
