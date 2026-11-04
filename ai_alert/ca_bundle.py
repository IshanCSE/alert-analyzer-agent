"""Automatic CA certificate bundle discovery and management."""

import os
from pathlib import Path
from typing import Optional

from ai_alert.logger import get_logger

logger = get_logger("ca_bundle")


def get_ca_bundle() -> Optional[str]:
    """
    Discover and return the CA certificate bundle path.

    Search order:
    1. Environment variables (SSL_CERT_FILE, REQUESTS_CA_BUNDLE)
    2. Pre-built combined bundle (~/.ai-alert/ca-combined.pem)
    3. Project .ca-bundle config file
    4. Known internal cert locations:
       - ~/projects/awn/etc/pki/certs/awn-dev-chain.pem
       - ~/projects/awn/pkg/rtkretention/certs/awn-dev-chain.pem
    5. System CA bundle (certifi)

    Returns:
        Path to CA bundle file if found, None otherwise
    """

    # 1. Check environment variables (manual override takes priority)
    env_bundle = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if env_bundle and Path(env_bundle).exists():
        logger.debug(f"Using CA bundle from environment: {env_bundle}")
        return env_bundle

    # 2. Check for pre-built combined bundle (includes Sentry + internal gateway certs)
    combined_bundle = Path.home() / ".ai-alert" / "ca-combined.pem"
    if combined_bundle.exists():
        logger.debug(f"Using combined CA bundle: {combined_bundle}")
        return str(combined_bundle)

    # 3. Check project-level config file
    project_root = Path(__file__).parent.parent
    project_bundle = project_root / ".ca-bundle"
    if project_bundle.exists():
        bundle_path = project_bundle.read_text().strip()
        if Path(bundle_path).exists():
            logger.debug(f"Using CA bundle from project config: {bundle_path}")
            return bundle_path

    # 4. Check ~/.claude/settings.json for NODE_EXTRA_CA_CERTS (for reference only)
    settings_file = Path.home() / ".claude" / "settings.json"
    if settings_file.exists():
        try:
            import json
            with open(settings_file) as f:
                settings = json.load(f)
                env_vars = settings.get("env", {})
                node_ca = env_vars.get("NODE_EXTRA_CA_CERTS")
                if node_ca:
                    # This is usually a devcontainer path, but might hint where certs are
                    logger.debug(f"Found NODE_EXTRA_CA_CERTS in settings: {node_ca} (devcontainer path)")
        except Exception as e:
            logger.debug(f"Could not parse settings.json: {e}")

    # 5. Check known Arctic Wolf cert locations
    awn_cert_paths = [
        Path.home() / "projects" / "awn" / "etc" / "pki" / "certs" / "awn-dev-chain.pem",
        Path.home() / "projects" / "awn" / "pkg" / "rtkretention" / "certs" / "awn-dev-chain.pem",
    ]

    for cert_path in awn_cert_paths:
        if cert_path.exists():
            logger.debug(f"Found AWN dev chain certificate: {cert_path}")
            # On first use, build combined bundle for faster subsequent runs
            logger.info("Building combined CA bundle (includes Sentry + gateway certs)...")
            combined = build_combined_ca_bundle()
            if combined:
                return combined
            return str(cert_path)

    # 6. Fallback: Python's certifi (may not work with corporate proxy)
    try:
        import certifi
        logger.debug(f"Using Python certifi: {certifi.where()}")
        return certifi.where()
    except ImportError:
        logger.warning("certifi not installed")
        return None


def build_combined_ca_bundle() -> Optional[str]:
    """
    Build a combined CA bundle with all needed certificates.

    Combines:
    1. AWN dev chain (for internal gateway)
    2. Sentry cert chain (for arcticwolf.sentry.io)
    3. Anthropic cert chain (for api.anthropic.com, if needed)

    Caches result at ~/.ai-alert/ca-combined.pem

    Returns:
        Path to combined CA bundle file
    """
    import subprocess
    import tempfile

    combined_path = Path.home() / ".ai-alert" / "ca-combined.pem"
    combined_path.parent.mkdir(parents=True, exist_ok=True)

    certs_to_fetch = [
        ("arcticwolf.sentry.io", 443),
        ("llm-gateway.us002-dev.rtkwlf.io", 443),
    ]

    combined_certs = []

    # Add AWN dev chain (already trusted for internal gateway)
    awn_chain = Path.home() / "projects" / "awn" / "etc" / "pki" / "certs" / "awn-dev-chain.pem"
    if awn_chain.exists():
        try:
            combined_certs.append(awn_chain.read_text())
            logger.debug(f"Added AWN dev chain: {awn_chain}")
        except Exception as e:
            logger.warning(f"Could not read AWN chain: {e}")

    # Fetch and add certificates for external services
    for host, port in certs_to_fetch:
        try:
            logger.debug(f"Fetching cert chain for {host}:{port}...")
            result = subprocess.run(
                f"openssl s_client -connect {host}:{port} -showcerts < /dev/null 2>/dev/null | "
                f"sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout:
                combined_certs.append(result.stdout)
                logger.debug(f"Added cert chain for {host}")
            else:
                logger.warning(f"No certs returned from {host}")
        except Exception as e:
            logger.warning(f"Could not fetch cert from {host}: {e}")

    # Write combined bundle
    if combined_certs:
        try:
            combined_pem = "\n".join(combined_certs)
            combined_path.write_text(combined_pem)
            logger.info(f"Built combined CA bundle: {combined_path} ({len(combined_pem)} bytes)")
            return str(combined_path)
        except Exception as e:
            logger.error(f"Could not write combined CA bundle: {e}")

    return None


def cache_discovered_bundle() -> Optional[str]:
    """
    Discover CA bundle and cache it in project .ca-bundle file.

    This allows quick retrieval on subsequent runs without re-searching.

    Returns:
        Path to CA bundle file
    """
    bundle_path = get_ca_bundle()

    if bundle_path:
        try:
            project_root = Path(__file__).parent.parent
            config_file = project_root / ".ca-bundle"
            config_file.write_text(bundle_path)
            logger.info(f"Cached CA bundle path: {bundle_path}")
        except Exception as e:
            logger.warning(f"Could not cache CA bundle: {e}")

    return bundle_path
