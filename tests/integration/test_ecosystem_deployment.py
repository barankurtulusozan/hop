import os
import pytest
import yaml

from src.cli.runner import HOPCLIRunner


@pytest.mark.asyncio
async def test_ecosystem_deployment_integration():
    # 1. CLI runner verification
    runner = HOPCLIRunner()
    res = await runner.run(["serve", "--port", "8000"])
    assert res.exit_code == 0

    # 2. OpenAPI 3.0 specification validation
    openapi_path = "/Users/barankurtulusozan/hop/docs/openapi.yaml"
    assert os.path.exists(openapi_path)
    with open(openapi_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    assert spec["openapi"] == "3.0.3"
    assert "/v1/chat/completions" in spec["paths"]
    assert "/v1/agents/run" in spec["paths"]

    # 3. Deployment manifests validation
    dockerfile_path = "/Users/barankurtulusozan/hop/deploy/Dockerfile"
    compose_path = "/Users/barankurtulusozan/hop/deploy/docker-compose.yml"
    k8s_path = "/Users/barankurtulusozan/hop/deploy/k8s/deployment.yaml"

    assert os.path.exists(dockerfile_path)
    assert os.path.exists(compose_path)
    assert os.path.exists(k8s_path)
