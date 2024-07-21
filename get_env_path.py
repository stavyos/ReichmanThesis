from pathlib import Path


def get_env_path() -> Path:
    return Path.joinpath(Path(__file__).parent.absolute(), '.env')
