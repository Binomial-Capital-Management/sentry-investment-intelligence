"""
Kafka configuration - all settings from environment variables.
NO HARDCODING as per CODING_RULES.md
"""
import os
import ssl
from typing import Optional, Dict


class KafkaConfig:
    """
    All Kafka settings from environment.
    Enabled by default for development.
    """
    
    def __init__(self):
        # Feature flag - enabled by default for development
        self.enabled = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
        
        # Connection settings
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

        # Security settings (env-driven; defaults keep things simple)
        # Common MSK configs:
        # - security protocol: SSL (TLS without auth) or SASL_SSL (TLS + SASL)
        # - For SASL/SCRAM, set username/password and mechanism, e.g., SCRAM-SHA-512
        self.security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").upper()
        self.sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISM")  # e.g., SCRAM-SHA-512
        self.sasl_username = os.getenv("KAFKA_SASL_USERNAME")
        self.sasl_password = os.getenv("KAFKA_SASL_PASSWORD")
        # Optional custom CA file path if needed (MSK generally uses public CA)
        self.ssl_cafile = os.getenv("KAFKA_SSL_CAFILE")
        self.ssl_check_hostname = os.getenv("KAFKA_SSL_CHECK_HOSTNAME", "true").lower() == "true"
        
        # Topics
        self.topic_prices = os.getenv("KAFKA_TOPIC_PRICES", "price-updates")
        self.topic_screener = os.getenv("KAFKA_TOPIC_SCREENER", "screener-data")
        
        # Consumer settings
        self.consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "binomial-consumer")
        self.auto_offset_reset = os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest")
        
        # Performance settings
        self.max_poll_records = int(os.getenv("KAFKA_MAX_POLL_RECORDS", "10"))
        self.session_timeout_ms = int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "10000"))

        # Connection timeout settings for fast failure
        self.request_timeout_ms = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "30000"))
        self.metadata_max_age_ms = int(os.getenv("KAFKA_METADATA_MAX_AGE_MS", "300000"))
        
        # Queue and buffer settings for ScreenerHub
        self.max_queue_size = int(os.getenv("KAFKA_MAX_QUEUE_SIZE", "100"))
        self.snapshot_size = int(os.getenv("KAFKA_SNAPSHOT_SIZE", "20"))
        self.websocket_send_timeout = float(os.getenv("KAFKA_WS_SEND_TIMEOUT", "5.0"))
        
        # Streaming optimization settings
        self.screener_update_interval = float(os.getenv("SCREENER_UPDATE_INTERVAL", "30"))
        self.screener_batch_size = int(os.getenv("SCREENER_BATCH_SIZE", "5"))
        self.screener_max_concurrent = int(os.getenv("SCREENER_MAX_CONCURRENT", "10"))
    
    def is_enabled(self) -> bool:
        """Check if Kafka streaming is enabled"""
        return self.enabled
    
    def build_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Build an SSL context if SSL is required by security protocol.
        Uses strict SSL verification for AWS MSK compatibility.
        """
        if self.security_protocol not in ("SSL", "SASL_SSL"):
            return None

        # Create strict SSL context for AWS MSK
        context = ssl.create_default_context(cafile=self.ssl_cafile) if self.ssl_cafile else ssl.create_default_context()

        # AWS MSK requires strict SSL verification
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = self.ssl_check_hostname

        # Ensure minimum TLS version for security
        if hasattr(ssl, "TLSVersion"):
            context.minimum_version = ssl.TLSVersion.TLSv1_2

        # Load CA certificates if needed (AWS containers should have these)
        if not self.ssl_cafile:
            try:
                # Try common CA bundle locations for AWS containers
                ca_paths = ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]
                for ca_path in ca_paths:
                    try:
                        context.load_verify_locations(cafile=ca_path)
                        break
                    except FileNotFoundError:
                        continue
            except Exception:
                pass  # Use default CA bundle

        return context

    def get_client_security_kwargs(self) -> Dict[str, object]:
        """Return security-related kwargs for aiokafka clients (producer/consumer)."""
        kwargs: Dict[str, object] = {}
        if self.security_protocol and self.security_protocol != "PLAINTEXT":
            kwargs["security_protocol"] = self.security_protocol
            ssl_ctx = self.build_ssl_context()
            if ssl_ctx is not None:
                kwargs["ssl_context"] = ssl_ctx
        # SASL (optional)
        if self.sasl_mechanism and self.sasl_username and self.sasl_password:
            kwargs["sasl_mechanism"] = self.sasl_mechanism
            kwargs["sasl_plain_username"] = self.sasl_username
            kwargs["sasl_plain_password"] = self.sasl_password
        return kwargs

    def get_producer_config(self) -> Dict[str, object]:
        """Get config dict for aiokafka producer."""
        cfg: Dict[str, object] = {
            "bootstrap_servers": self.bootstrap_servers,
        }
        cfg.update(self.get_client_security_kwargs())
        return cfg

    def get_consumer_config(self) -> dict:
        """Get config dict for aiokafka consumer"""
        cfg: Dict[str, object] = {
            'bootstrap_servers': self.bootstrap_servers,
            'group_id': self.consumer_group,
            'auto_offset_reset': self.auto_offset_reset,
            'max_poll_records': self.max_poll_records,
            'session_timeout_ms': self.session_timeout_ms,
            'enable_auto_commit': True,  # Simple for PoC
        }
        cfg.update(self.get_client_security_kwargs())
        return cfg