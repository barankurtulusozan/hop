import pytest

from src.cli.runner import HOPCLIRunner


@pytest.mark.asyncio
async def test_cli_runner_subcommands():
    runner = HOPCLIRunner()

    # 1. hop serve
    res_serve = await runner.run(["serve", "--port", "9000"])
    assert res_serve.exit_code == 0
    assert res_serve.output["port"] == 9000

    # 2. hop eval_run
    res_eval = await runner.run(["eval_run", "--suite", "benchmark_v1"])
    assert res_eval.exit_code == 0
    assert res_eval.output["suite"] == "benchmark_v1"

    # 3. hop queue_status
    res_queue = await runner.run(["queue_status"])
    assert res_queue.exit_code == 0
    assert "dlq_count" in res_queue.output

    # 4. hop cost_summary
    res_cost = await runner.run(["cost_summary", "--tenant", "acme_org"])
    assert res_cost.exit_code == 0
    assert res_cost.output["tenant_id"] == "acme_org"

    # 5. hop security_verify
    res_sec = await runner.run(["security_verify", "--token", "Bearer_12345"])
    assert res_sec.exit_code == 0
    assert res_sec.output["verified"] is True
