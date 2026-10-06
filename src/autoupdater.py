import logging
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import TypedDict, cast

import httpx

import src.logger
from src import __version__
from src.release_payload import stage_release
from src.release_versions import is_newer_version, is_prerelease, select_latest_release

LOGGER = logging.getLogger(__name__)
RELEASE_REPO_OWNER = "ytwytw"
RELEASE_REPO_NAME = "d4lf"


ReleaseAsset = TypedDict("ReleaseAsset", {"name": str, "browser_download_url": str})  # ruff: ignore[convert-typed-dict-functional-to-class]
ReleaseData = TypedDict("ReleaseData", {"tag_name": str, "assets": list[ReleaseAsset]}, total=False)  # ruff: ignore[convert-typed-dict-functional-to-class]


# This autoupdater was almost entirely provided by iAmPilcrow
class D4LFUpdater:
    def __init__(self) -> None:
        self.repo_owner = RELEASE_REPO_OWNER
        self.repo_name = RELEASE_REPO_NAME
        self.api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        self.releases_api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases?per_page=100"
        self.changes_base_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/compare/"
        self.current_dir = Path.cwd()
        self.temp_dir = self.current_dir / "temp_update"
        self.version_file = self.temp_dir / "version"

    @staticmethod
    def normalize_version(version: str | None) -> str | None:
        """Ensure version has 'v' prefix."""
        if version is None:
            return None
        return "v" + version.strip().removeprefix("v").removeprefix("V")

    def get_latest_release(self, silent: bool = False) -> ReleaseData | None:
        """Fetch latest release info from GitHub API."""
        if not silent:
            LOGGER.info("Checking for latest release...")
        try:
            current_version = self.normalize_version(__version__) or ""
            api_url = self.releases_api_url if self._is_prerelease(current_version) else self.api_url
            response = httpx.get(api_url, timeout=10)
            response.raise_for_status()
            release_data = response.json()
            releases = release_data if isinstance(release_data, list) else [release_data]
            selected = select_latest_release(release for release in releases if isinstance(release, dict))
            return cast("ReleaseData | None", selected)
        except (httpx.HTTPError, OSError, ValueError) as e:
            LOGGER.error(f"Error fetching release info: {e}")
            return None

    _is_prerelease = staticmethod(is_prerelease)
    is_newer_version = staticmethod(is_newer_version)

    def print_changes_between_releases(self, current_version: str, latest_version: str) -> None:
        try:
            url = self.changes_base_url + current_version + "..." + latest_version
            response = httpx.get(url, timeout=10)
            response.raise_for_status()

            LOGGER.info("Changes since last update:")
            for commit in response.json()["commits"]:
                LOGGER.info(f"- {commit['commit']['message']}")
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as e:
            LOGGER.error(f"Error fetching changes since last update: {e}")

    @staticmethod
    def download_file(url: str, filename: Path) -> bool:
        """Download file with progress indication."""
        LOGGER.info(f"Downloading {filename}...")
        try:
            with httpx.stream("GET", url, timeout=30, follow_redirects=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                with filename.open("wb") as output:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        output.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            print(f"\rProgress: {(downloaded / total_size) * 100:.1f}%", end="")
                print("\n")
        except (httpx.HTTPError, OSError, ValueError) as e:
            LOGGER.error(f"\nError downloading file: {e}")
            return False
        LOGGER.info("Download complete!")
        return True

    def extract_release(self, zip_path: Path, latest_version: str) -> bool:
        """Extract zip so batch process can copy files."""
        LOGGER.info("Extracting files...")

        try:
            stage_release(zip_path, self.temp_dir)
            Path(self.version_file).write_text(latest_version, encoding="utf-8")
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, zipfile.LargeZipFile) as e:
            LOGGER.error(f"Error during extraction: {e}")
            return False
        LOGGER.info("Files extracted successfully!")
        return True

    @staticmethod
    def _get_major_version_number(version: str) -> int:
        return int(version.replace("v", "").split(".")[0])

    def preprocess(self) -> bool:
        """Main update process.

        This will:
        - Check if update is needed
        - Download new release
        - Extract files to a temp directory
        Additional updating and cleanup will be handled by the post process
        """
        self._print_header()

        # Get current installed version
        current_version = self.normalize_version(__version__) or ""
        LOGGER.info(f"Current installed version: {current_version}")

        # Get latest release info
        release_data = self.get_latest_release()
        if not release_data:
            LOGGER.warning("Unable to find latest release on github, can't automatically update.")
            return False

        latest_version = self.normalize_version(release_data.get("tag_name")) or ""
        LOGGER.info(f"Latest release tag: {latest_version}")

        # Check if update needed
        if not self.is_newer_version(latest_version, current_version):
            LOGGER.info("✓ No newer release is available.")
            input("\nPress Enter to exit...")
            sys.exit(2)

        LOGGER.info(f"→ Update available: {current_version} → {latest_version}")
        self.print_changes_between_releases(current_version, latest_version)

        # Check if it's an update to a major version and warn of the consequences
        if self._get_major_version_number(latest_version) > self._get_major_version_number(current_version):
            LOGGER.warning(
                "You are upgrading a major version. This means your existing profiles might no longer work and will need to be reimported or recreated. Do you want to proceed?"
            )
            proceed = input("Enter yes or y to proceed, all other inputs will cancel: ")
            if proceed.lower() not in ["yes", "y"]:
                LOGGER.info("Cancelling update.")
                return False
        # Find the d4lf zip asset
        assets = release_data.get("assets", [])
        zip_asset = None

        for asset in assets:
            if asset["name"] == f"d4lf_{latest_version}.zip":
                zip_asset = asset
                break

        if not zip_asset:
            LOGGER.error("Could not find d4lf zip file in release assets.")
            return False

        # Create temp directory
        self.temp_dir.mkdir(exist_ok=True)

        download_url = zip_asset["browser_download_url"]
        zip_filename = self.temp_dir / zip_asset["name"]

        LOGGER.info("")
        # Download
        if not self.download_file(download_url, zip_filename):
            return False

        # Extract the zip
        if not self.extract_release(zip_filename, latest_version):
            return False
        LOGGER.info("=" * 50)
        LOGGER.info("✓ Preprocessing is done, shutting down to allow update to happen. A new window will open shortly.")
        LOGGER.info("=" * 50)
        return True

    def postprocess(self) -> bool:
        """Post process will handle the cleanup.

        It will:
        - Delete the temporary files that were extracted
        - Verify the version is truly updated
        """
        self._print_header()
        with self.version_file.open("r") as f:
            updated_to_version = f.read().strip()

        if not updated_to_version:
            LOGGER.error(
                "Pre-processing update data was missing! Try to update manually by downloading the newest D4LF release."
            )
            return False

        current_version = self.normalize_version(__version__) or ""
        if updated_to_version != current_version:
            LOGGER.error(
                f"Current version is {current_version} but we attempted to update to {updated_to_version}. Check logs for errors and update manually."
            )
            return False

        LOGGER.info("Cleaning up temporary files")
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        LOGGER.info("Temporary files are removed")
        LOGGER.info("=" * 50)
        LOGGER.info(f"✓ Successfully updated to {updated_to_version}!")
        LOGGER.info("=" * 50)
        return True

    @staticmethod
    def _print_header() -> None:
        LOGGER.info("=" * 50)
        LOGGER.info("D4LF Auto-Updater")
        LOGGER.info("=" * 50)
        LOGGER.info("")


def start_auto_update(postprocess: bool = False) -> None:
    updater = D4LFUpdater()
    try:
        success = updater.postprocess() if postprocess else updater.preprocess()
        input("\nPress Enter to exit...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        LOGGER.warning("\n\nUpdate cancelled by user.")
        sys.exit(1)
    except Exception:
        LOGGER.exception("\n\nUnexpected error during auto-update")
        input("\nPress Enter to exit...")
        sys.exit(1)


def notify_if_update() -> None:
    if not _should_check_for_update():
        LOGGER.debug("Still within 4 hours of previous update check, skipping automatic update check.")
        return

    updater = D4LFUpdater()
    current_version = updater.normalize_version(__version__) or ""

    release = updater.get_latest_release(silent=True)
    if not release:
        LOGGER.warning("Unable to find latest release of d4lf on github, skipping check for updates.")
        return

    latest_version = updater.normalize_version(release.get("tag_name")) or ""
    if updater.is_newer_version(latest_version, current_version):
        LOGGER.info("=" * 50)
        LOGGER.info(
            f"An update has been detected. Run autoupdater.bat to update. Version {current_version} → {latest_version}"
        )
        updater.print_changes_between_releases(current_version=current_version, latest_version=latest_version)
        LOGGER.info("=" * 50)


def _should_check_for_update(check_interval_hours: float = 4) -> bool:
    """Check if it's time to check for updates based on a cooldown period."""
    check_file = Path.cwd() / "assets" / "last_update"
    current_time = time.time()
    last_check_time = 0

    # Read the last check time from file if it exists
    try:
        if check_file.exists():
            last_check_time = float(check_file.read_text(encoding="utf-8").strip())
    except OSError, ValueError:
        LOGGER.debug("Ignoring unreadable update-check timestamp", exc_info=True)

    # Calculate elapsed time since last check
    elapsed_time = current_time - last_check_time

    # Check if enough time has passed
    if elapsed_time >= (check_interval_hours * 3600):
        # Update the last check time
        try:
            check_file.parent.mkdir(parents=True, exist_ok=True)
            check_file.write_text(str(current_time), encoding="utf-8")
        except OSError:
            LOGGER.debug("Could not save update-check timestamp", exc_info=True)
        return True
    return False


if __name__ == "__main__":
    src.logger.setup(log_level="debug")
    start_auto_update()
