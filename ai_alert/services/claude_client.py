"""Claude API client for analyzing Sentry alerts."""

import json
from typing import Optional, Tuple
import anthropic

from ai_alert.logger import get_logger
from ai_alert.models import Recommendation

logger = get_logger("claude_client")


class ClaudeClient:
    """Client for Claude API analysis."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5-5",
        max_tokens: int = 2048,
    ):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key
            model: Model ID (default: claude-sonnet-5-5, override to claude-opus-5-5 for complex cases)
            max_tokens: Maximum tokens in response
        """
        import os
        import json
        from pathlib import Path
        import httpx

        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = None
        self.auth_token = None

        # Check for Claude settings (internal Anthropic gateway)
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")

        if not base_url or not auth_token:
            # Try to load from ~/.claude/settings.json
            settings_file = Path.home() / ".claude" / "settings.json"
            if settings_file.exists():
                try:
                    with open(settings_file) as f:
                        settings = json.load(f)
                        env = settings.get("env", {})
                        if "ANTHROPIC_BASE_URL" in env:
                            base_url = env["ANTHROPIC_BASE_URL"]
                        if "ANTHROPIC_AUTH_TOKEN" in env:
                            auth_token = env["ANTHROPIC_AUTH_TOKEN"]
                except Exception as e:
                    logger.debug(f"Could not load settings.json: {e}")

        # Use auth token from settings if available (overrides api_key for gateway auth)
        if auth_token and base_url:
            api_key = auth_token
            self.auth_token = auth_token
            self.base_url = base_url
            logger.debug("Using ANTHROPIC_AUTH_TOKEN from settings")

            # Translate standard model aliases to gateway-specific model IDs.
            # The internal gateway only serves a fixed allowlist of model names
            # (Bedrock-prefixed, mostly); public SDK aliases like "claude-sonnet-5-5"
            # are rejected with a 403 team_model_access_denied error.
            gateway_model_map = {
                "claude-sonnet-5-5": "bedrock-claude-5-0-sonnet",
                "claude-opus-5-5": "bedrock-claude-4-8-opus",
                "claude-haiku-5-5": "bedrock-claude-5-5-haiku",
            }
            if model in gateway_model_map:
                translated = gateway_model_map[model]
                logger.debug(f"Translating model '{model}' -> '{translated}' for gateway")
                model = translated
                self.model = translated

        # Auto-discover and apply CA bundle
        from ai_alert.ca_bundle import get_ca_bundle
        ca_bundle = get_ca_bundle()
        if ca_bundle:
            logger.debug(f"Claude client using CA bundle: {ca_bundle}")

        self.ca_bundle = ca_bundle
        http_client = None
        if ca_bundle:
            # Use custom CA certificate for internal gateways/proxies
            try:
                http_client = httpx.Client(verify=ca_bundle)
                logger.debug(f"Created httpx client with CA bundle: {ca_bundle}")
            except Exception as e:
                logger.warning(f"Failed to create httpx client with CA bundle: {e}")

        if base_url:
            try:
                if http_client:
                    self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url, http_client=http_client)
                else:
                    self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
                logger.info(f"Claude client initialized with model={model}, base_url={base_url}")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic with gateway: {e}")
                # Fallback to default
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info(f"Claude client initialized with model={model} (fallback)")
        else:
            if http_client:
                self.client = anthropic.Anthropic(api_key=api_key, http_client=http_client)
            else:
                self.client = anthropic.Anthropic(api_key=api_key)
            logger.info(f"Claude client initialized with model={model}")

    def _analyze_direct_httpx(
        self, system_prompt: str, user_prompt: str
    ) -> Tuple[Optional[str], int]:
        """Fallback: call Claude API directly via httpx, bypassing Anthropic SDK.

        This is used if the SDK fails (e.g., auth issues with custom gateways).

        Returns:
            Tuple of (response_text, tokens_used), or (None, 0) if fails
        """
        if not self.base_url or not self.auth_token:
            logger.debug("No custom gateway configured, cannot use direct httpx")
            return None, 0

        try:
            import httpx

            # Try both auth header formats
            headers_options = [
                {"Authorization": f"Bearer {self.auth_token}"},
                {"x-api-key": self.auth_token},
            ]

            for headers in headers_options:
                try:
                    logger.debug(f"Trying direct httpx with headers: {list(headers.keys())}")
                    client = httpx.Client(verify=self.ca_bundle if self.ca_bundle else True)

                    response = client.post(
                        f"{self.base_url}/v1/messages",
                        headers={
                            **headers,
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "max_tokens": self.max_tokens,
                            "system": system_prompt,
                            "messages": [{"role": "user", "content": user_prompt}],
                        },
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        resp_json = response.json()
                        content = resp_json.get("content", [{}])[0].get("text", "")
                        tokens = resp_json.get("usage", {})
                        tokens_used = tokens.get("output_tokens", 0) + tokens.get("input_tokens", 0)
                        logger.info(f"Direct httpx succeeded with header: {list(headers.keys())[0]}")
                        return content, tokens_used
                    elif response.status_code == 401:
                        logger.debug(f"Auth failed with {list(headers.keys())[0]}: {response.text[:100]}")
                        continue  # Try next header format
                    else:
                        logger.warning(f"Direct httpx HTTP {response.status_code}: {response.text[:200]}")
                        continue

                except httpx.RequestError as e:
                    logger.debug(f"Direct httpx request error: {e}")
                    continue

                finally:
                    client.close()

            logger.error("Direct httpx failed with all auth header formats")
            return None, 0

        except Exception as e:
            logger.error(f"Direct httpx exception: {e}")
            return None, 0

    def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[Recommendation, int]:
        """Call Claude API with structured JSON output.

        Args:
            system_prompt: System prompt (cx-collector architecture context)
            user_prompt: User prompt (Sentry event + evidence)

        Returns:
            Tuple of (Recommendation object, tokens_used)

        Raises:
            anthropic.APIError: On API errors
        """
        logger.debug(f"Calling Claude with model={self.model}")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )

            # Extract response content
            content = response.content[0].text
            tokens_used = response.usage.output_tokens + response.usage.input_tokens

        except anthropic.APIError as e:
            # If SDK fails, try direct httpx approach
            logger.warning(f"SDK request failed ({e}), trying direct httpx approach")
            content, tokens_used = self._analyze_direct_httpx(system_prompt, user_prompt)
            if not content:
                raise

        # Parse JSON from response
        try:
            # Try to find JSON in the response (Claude might wrap it in markdown code blocks)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content

            recommendation_dict = json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Raw response: {content}")
            raise ValueError(f"Claude response is not valid JSON: {e}") from e

        # Convert to Recommendation model
        recommendation = Recommendation(**recommendation_dict)

        logger.info(f"Claude analysis complete: {tokens_used} tokens used")
        logger.debug(f"Recommendation: {recommendation.summary[:100]}...")

        return recommendation, tokens_used


def build_system_prompt() -> str:
    """Build system prompt with cx-collector architecture context.

    Returns:
        System prompt string
    """
    return """You are an expert Go developer and SRE analyzing Sentry error alerts from the cx-collector service (https://github.com/arcticwolf/cx-collector).

cx-collector is a background worker that:
- Collects telemetry from multiple upstream services (Salesforce, Slack, Jira, etc.)
- Writes metrics to Amazon Timestream for InfluxDB
- Writes metric snapshots to PostgreSQL
- Runs continuously on a fixed schedule with a job pool

Key Architecture Patterns:
1. Collector Interface: Each data source has a Collector that implements Run(ctx) -> error
2. Component Registry: Collectors registered with constant names like "alerts-count", "scanners-health"
3. Dependency Injection: Collectors receive (tsdb.Writer, data.Datastore, *zap.Logger, *config.Config) via collector.Deps
4. Error Capture: Errors reported via tracing.CaptureException(err) (Sentry integration)
5. Error Taxonomy: api_error, parse_error, uuid_error, timeout, constraint_violation, decode_error

Common Error Patterns:
- nil pointer dereference: missing nil check before field access
- JSON parse errors: malformed upstream API response
- UUID parse errors: invalid format in data
- Timeout errors: upstream service slow/down
- Constraint violations: duplicate keys, data conflicts

Your task:
1. Analyze the Sentry error event (stack trace, tags, breadcrumbs)
2. Correlate with cx-collector code context (if provided)
3. Identify root cause and affected component
4. Provide structured recommendation in JSON format

Output ONLY valid JSON matching this schema:
{
  "summary": "one-line summary of the root cause",
  "suggested_fix": "concrete fix recommendation with code context if applicable",
  "files_to_inspect": ["list of files to review"],
  "related_code_paths": ["list of related collector/client paths"],
  "follow_up_actions": ["list of follow-up actions: review, test, monitor, etc"],
  "is_known_issue": false
}

Be concise, specific, and actionable."""


def build_user_prompt(
    sentry_event: Optional[dict] = None,
    code_context: str = "",
    cloudwatch_logs: str = "",
) -> str:
    """Build user prompt from Sentry event and optional evidence.

    Args:
        sentry_event: Full Sentry event JSON (can be None or empty dict)
        code_context: Optional code snippets from stack frames
        cloudwatch_logs: Optional CloudWatch logs around error time

    Returns:
        User prompt string
    """
    # Handle None or empty event
    if not sentry_event:
        sentry_event = {}

    prompt = "Analyze this Sentry error:\n\n"

    # Event summary
    if "exception" in sentry_event and sentry_event["exception"]["values"]:
        exc = sentry_event["exception"]["values"][0]
        prompt += f"**Error Type:** {exc.get('type', 'Unknown')}\n"
        prompt += f"**Error Value:** {exc.get('value', 'N/A')}\n\n"

    # Stack trace
    if "exception" in sentry_event and sentry_event["exception"]["values"]:
        exc = sentry_event["exception"]["values"][0]
        if "stacktrace" in exc and exc["stacktrace"]["frames"]:
            prompt += "**Stack Trace:**\n"
            for i, frame in enumerate(exc["stacktrace"]["frames"]):
                prompt += f"  {i+1}. {frame.get('filename', 'unknown')}:{frame.get('lineno', '?')} in {frame.get('function', '?')}\n"
            prompt += "\n"

    # Tags (metadata)
    if "tags" in sentry_event and sentry_event["tags"]:
        prompt += "**Context Tags:**\n"
        # Handle both dict and list formats
        if isinstance(sentry_event["tags"], dict):
            for key, value in sentry_event["tags"].items():
                prompt += f"  {key}: {value}\n"
        elif isinstance(sentry_event["tags"], list):
            for tag in sentry_event["tags"]:
                if isinstance(tag, dict):
                    prompt += f"  {tag.get('key', 'unknown')}: {tag.get('value', 'N/A')}\n"
        prompt += "\n"

    # Breadcrumbs (event history)
    if "breadcrumbs" in sentry_event and sentry_event["breadcrumbs"]:
        prompt += "**Event Breadcrumbs:**\n"
        for crumb in sentry_event["breadcrumbs"][-5:]:  # Last 5 breadcrumbs
            prompt += f"  [{crumb.get('timestamp', 'N/A')}] {crumb.get('level', 'info')}: {crumb.get('message', crumb.get('type', 'event'))}\n"
        prompt += "\n"

    # Code context
    if code_context:
        prompt += "**Relevant Code Context:**\n"
        prompt += code_context
        prompt += "\n"

    # CloudWatch logs
    if cloudwatch_logs:
        prompt += "**Related Logs:**\n"
        prompt += cloudwatch_logs
        prompt += "\n"

    return prompt
