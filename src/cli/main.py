import asyncio
import sys
from src.cli.runner import HOPCLIRunner


def main():
    runner = HOPCLIRunner()
    result = asyncio.run(runner.run(sys.argv[1:]))
    print(f"[{result.status.upper()}] Command: {result.command}")
    for k, v in result.output.items():
        print(f"  {k}: {v}")
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
