"""Challenge-specific health check for the shared KotH demo."""

from lib import KothContext, expect_text, koth_checker


@koth_checker
def check(context: KothContext) -> None:
    expect_text(context, "/health", "ok")


if __name__ == "__main__":
    raise SystemExit(check())
