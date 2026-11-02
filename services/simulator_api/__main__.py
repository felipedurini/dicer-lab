"""Run the persistent simulator API as one HTTP process plus one worker child."""

import uvicorn

from .settings import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "services.simulator_api.app:app",
        host=settings.api_host,
        port=settings.port,
        workers=1,
        reload=False,
        log_level=settings.log_level.lower(),
        access_log=False,
        server_header=False,
        date_header=False,
    )


if __name__ == "__main__":
    main()
