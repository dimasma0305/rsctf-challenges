"""Challenge-specific checks for the platform-hosted A&D demo."""

from lib import AdContext, ad_checker, expect_text


@ad_checker
def check(context: AdContext) -> None:
    expect_text(context, "/health", "ok")
    expect_text(context, "/flag", context.flag)


if __name__ == "__main__":
    raise SystemExit(check())
