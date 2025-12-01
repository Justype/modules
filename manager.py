#!/usr/bin/env python3
import os
import platform
import sys
import urllib.request
import stat
import subprocess
import json
import re
import csv
import shutil
import argparse
import time
from typing import Dict, List, Optional

def main():
    parser = argparse.ArgumentParser(description="Package Manager")
    parser.add_argument("-i", "--install", type=str, help="<package>/<version> to install")
    parser.add_argument("-u", "--update-local", action="store_true", help="Update local packages from build-scripts")
    parser.add_argument("-U", "--update", action="store_true", help="Update package versions in the database")
    parser.add_argument("-a", "--add", type=str, help="Add a new <package> to the database")
    parser.add_argument("-s", "--search", type=str, help="Search for <term> in package names and descriptions")
    parser.add_argument("-l", "--list", action="store_true", help="List all packages")
    parser.add_argument("-li", "--list-installed", action="store_true", help="List installed packages (not implemented, please use ml av)")
    parser.add_argument("-I", "--info", type=str, help="<package> to show detailed info")
    parser.add_argument("-d", "--delete", type=str, help="<package>/<version> to delete")
    parser.add_argument("--print-package-version", type=str, help="INPUT: <package>/<version> or <package>, STDOUT: matched package/version (internal use)")
    parser.add_argument("--print-dependencies", type=str, help="<package>/<version> to print dependencies (internal use)")
    args = parser.parse_args()

    pm = PackageManager(Config.get_tsv_path())

    if args.update:
        pm.update_local_packages()
        pm.fetch_all_online_versions()
        pm.sort_packages()
        pm.save_to_tsv()
        Utils.print_stderr("Package versions updated.")
    elif args.update_local:
        pm.update_local_packages()
        pm.sort_packages()
        pm.save_to_tsv()
        Utils.print_stderr("Local packages updated from build-scripts.")
    elif args.add:
        success = pm.add_entry_from_name(args.add)
        if success:
            pm.save_to_tsv()
    elif args.install:
        package_name = ""
        version = ""
        try:
            package_name, version = pm.get_package_version(args.install)
            success = pm.install_package(package_name, version)
            if success:
                Utils.print_stderr(f"Successfully installed {Colorize.yellow(args.install)}.")
            else:
                Utils.print_stderr(f"Failed to install {Colorize.red(args.install)}.")
        except KeyboardInterrupt:
            Utils.print_stderr(f"Installation of {Colorize.red(args.install)} interrupted by user.")
            if package_name and version:
                pm.delete(package_name, version)
        except Exception as e:
            Utils.print_stderr(f"Error installing {Colorize.red(args.install)}: {e}")
            if package_name and version:
                pm.delete(package_name, version)
            Utils.print_stderr(f"For conda packages, make sure the {Colorize.yellow(args.install)} exists on Anaconda.org.")
            Utils.print_stderr(f"For local packages, run {Colorize.yellow('./manager.py -u')} to refresh the database.")
    elif args.delete:
        try:
            package_name, version = pm.get_package_version(args.delete)
            ready = input(f"Are you sure you want to delete {Colorize.yellow(package_name)}/{Colorize.yellow(version)}? [y/N]: ")
            if ready.lower() != 'y':
                Utils.print_stderr("Deletion cancelled by user.")
                sys.exit(0)
            success = pm.delete(package_name, version)
            if success:
                Utils.print_stderr(f"Successfully deleted {Colorize.yellow(args.delete)}.")
            else:
                Utils.print_stderr(f"Failed to delete {Colorize.red(args.delete)}.")
        except Exception as e:
            Utils.print_stderr(f"Error deleting {Colorize.red(args.delete)}: {e}")
    elif args.search:
        matches = pm.search_term(args.search)
        if matches:
            max_len = max(len(pkg.package) for pkg in matches)
            for pkg in matches:
                print(f"{Colorize.yellow(pkg.package.ljust(max_len))}: {pkg.whatis}")
        else:
            Utils.print_stderr(f"No packages found matching {Colorize.yellow(args.search)}.")
    elif args.list:
        pm.list_packages()
    elif args.info:
        pm.print_info(args.info)
    elif args.print_package_version:
        pm.print_package_version(args.print_package_version)
    elif args.print_dependencies:
        pm.print_dependencies(args.print_dependencies)
    
class Config:
    # TSV fields: package | tags | whatis | url | conda | versions
    script_dir         = os.path.dirname(os.path.abspath(__file__))
    # metadata_root      = os.path.join(script_dir, "metadata")      # Default metadata root
    metadata_root      = os.path.join(script_dir, "backup")
    executable_root    = os.path.join(script_dir, "bin")           # Default executable root
    build_scripts_root = os.path.join(script_dir, "build-scripts") # Default build scripts path
    apps_root          = os.path.join(script_dir, "apps")          # Default installation path
    ref_root           = os.path.join(script_dir, "ref")           # Default reference data path
    apps_modulefiles_root   = os.path.join(script_dir, "apps_modulefiles")   # Default modulefiles path
    ref_modulefiles_root = os.path.join(script_dir, "ref_modulefiles")  # Default ref modulefiles path
    micromamba_root    = os.path.join(script_dir, "conda")         # Default micromamba root
    
    @classmethod
    def get_tsv_path(cls) -> str:
        return os.path.join(cls.metadata_root, "packages.tsv")

    @classmethod
    def get_micromamba_path(cls, version: str = None) -> str:
        """Download micromamba if missing and return its path."""
        os.makedirs(cls.executable_root, exist_ok=True)
        micromamba_path = os.path.join(cls.executable_root, "micromamba")

        if os.path.exists(micromamba_path):
            return micromamba_path

        # Detect platform
        system = platform.system()
        if system == "Linux":
            PLATFORM = "linux"
        elif system == "Darwin":
            PLATFORM = "osx"
        elif "NT" in system:
            PLATFORM = "win"
        else:
            raise RuntimeError(f"Unsupported OS: {system}")

        # Detect architecture
        machine = platform.machine()
        if machine in ("aarch64", "ppc64le", "arm64"):
            ARCH = machine
        else:
            ARCH = "64"

        # Supported combinations
        supported = {"linux-aarch64", "linux-ppc64le", "linux-64",
                     "osx-arm64", "osx-64", "win-64"}
        combo = f"{PLATFORM}-{ARCH}"
        if combo not in supported:
            raise RuntimeError(f"Unsupported platform-arch combination: {combo}")

        # Determine URL
        if version is None:
            release_url = f"https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-{combo}"
        else:
            release_url = f"https://github.com/mamba-org/micromamba-releases/releases/download/{version}/micromamba-{combo}"

        Utils.print_stderr(f"Downloading micromamba from {release_url} ...")
        urllib.request.urlretrieve(release_url, micromamba_path)

        # Make executable
        st = os.stat(micromamba_path)
        os.chmod(micromamba_path, st.st_mode | stat.S_IEXEC)
        Utils.print_stderr(f"Micromamba downloaded and made executable at {Colorize.blue(micromamba_path)}")

        # Create a help script
        mm_path = os.path.join(os.path.abspath(cls.executable_root), "mm")
        with open(mm_path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/bash\n")
            f.write(f'"{os.path.abspath(micromamba_path)}" --root-prefix "{os.path.abspath(cls.micromamba_root)}" "$@"\n')
        st = os.stat(mm_path)
        os.chmod(mm_path, st.st_mode | stat.S_IEXEC)

        mm_create_path = os.path.join(os.path.abspath(cls.executable_root), "mm-create")
        with open(mm_create_path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/bash\n")
            f.write(f'"{os.path.abspath(micromamba_path)}" --root-prefix "{os.path.abspath(cls.micromamba_root)}" create -c conda-forge -c bioconda "$@"\n')
        st = os.stat(mm_create_path)
        os.chmod(mm_create_path, st.st_mode | stat.S_IEXEC)

        mm_install_path = os.path.join(os.path.abspath(cls.executable_root), "mm-install")
        with open(mm_install_path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/bash\n")
            f.write(f'"{os.path.abspath(micromamba_path)}" --root-prefix "{os.path.abspath(cls.micromamba_root)}" install -c conda-forge -c bioconda "$@"\n')
        st = os.stat(mm_install_path)
        os.chmod(mm_install_path, st.st_mode | stat.S_IEXEC)
        Utils.print_stderr(f"Micromamba helper script created at {Colorize.blue(cls.executable_root)}/mm")

        return micromamba_path

    @classmethod
    def get_search_command(cls, package: str) -> List[str]:
        return [
            cls.get_micromamba_path(), "--root-prefix", os.path.abspath(cls.micromamba_root),
            "search",
            "-c", "conda-forge", "-c", "bioconda",
            package,
            "--json"
        ]

    @classmethod
    def get_create_command(cls, package: str, version: str) -> List[str]:
        return [
            cls.get_micromamba_path(), "--root-prefix", os.path.abspath(cls.micromamba_root), 
            "create", "--prefix", os.path.join(cls.apps_root, package, version),
            "-c", "conda-forge", "-c", "bioconda", 
            f"{package}={version}", "-q", "-y"
        ]

class Utils:
    @staticmethod
    def print_stderr(message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", file=sys.stderr)

    @staticmethod
    def rmdir_until_not_empty(path: str):
        """Remove directories up to the first non-empty one."""
        current_path = path
        while True:
            try:
                os.rmdir(current_path)
            except OSError:
                break  # Directory not empty or other error
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:
                break  # Reached root
            current_path = parent_path
    

class Colorize:
    @staticmethod
    def red(text: str) -> str:
        return f'\033[91m{text}\033[0m'
    @staticmethod
    def blue(text: str) -> str:
        return f'\033[94m{text}\033[0m'
    @staticmethod
    def yellow(text: str) -> str:
        return f'\033[93m{text}\033[0m'
    @staticmethod
    def green(text: str) -> str:
        return f'\033[92m{text}\033[0m'

class Package:
    def __init__(self, package: str, tags: List[str], whatis: str, url: str, source: str):
        self.package = package
        self.tags = tags
        self.whatis = whatis
        self.url = url
        self.source = source  # conda channel or pypi or local
        self.versions: Optional[List[str]] = None  # unsorted versions

    def __repr__(self):
        return (f"Package(package={self.package!r}, tags={self.tags!r}, "
                f"whatis={self.whatis!r}, url={self.url!r}, source={self.source!r}, "
                f"versions={self.versions})")

    @staticmethod
    def new_from_string(data_str: str) -> 'Package':
        """
        Create a Package object from <package>/<version> or <package> string.
        """
        if "/" in data_str:
            package = data_str.split("/")[0]
        else:
            package = data_str
        tags = []
        whatis = ""
        url = ""
        source = "NA"

        return Package(package, tags, whatis, url, source)

    @staticmethod
    def parse_version_key(version: str) -> tuple:
        """
        Parse a version string into a tuple suitable for sorting.
        Numbers are converted to (num, '') and letters to (0, str)
        This allows comparing tuples like (1,22,'a') and (1,23,1)
        """
        components = re.findall(r'(\d+)|([a-zA-Z]+)', version)
        parsed_key = []
        for num_str, alpha_str in components:
            if num_str:
                parsed_key.append( (int(num_str), '') )   # numeric -> (num, '')
            elif alpha_str:
                parsed_key.append( (0, alpha_str) )      # letters -> (0, 'letters')
        return tuple(parsed_key)

    @staticmethod
    def version_order(versions: list[str], descending=True) -> list[str]:
        """
        Return the versions sorted numerically/lexicographically.
        """
        return sorted(versions, key=Package.parse_version_key, reverse=descending)

    def is_local(self) -> bool:
        """Return True if package is local"""
        return self.source == "NA" or self.source.lower() == "local" or self.source == "ref"
    
    def is_ref(self) -> bool:
        """Return True if package is reference data"""
        return self.source == "ref"

    def is_conda(self) -> bool:
        """Return True if package is from conda"""
        return self.source in ["conda-forge", "bioconda"]
    
    def is_pypi(self) -> bool:
        """Return True if package is from pypi"""
        return self.source.lower() == "pypi"

    def update_whatis_url(self, n_try: int = 3, delay: int = 2) -> bool:
        """Fetch whatis and url from Anaconda.org if conda!=NA."""
        if not self.is_conda():
            return True  # nothing to do
        
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            Utils.print_stderr("Required libraries 'requests' and 'beautifulsoup4' not installed.")
            Utils.print_stderr("Please install them via pip: pip install --user requests beautifulsoup4")
            Utils.print_stderr(f"If you want to update the whatis/url later, please rerun with {Colorize.yellow('-a')} {Colorize.yellow(self.package)}")
            return False

        url_page = f"https://anaconda.org/channels/{self.source}/packages/{self.package}/overview"

        for attempt in range(n_try):
            if attempt > 0:
                Utils.print_stderr(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            try:
                resp = requests.get(url_page)
                if resp.status_code != 200:
                    Utils.print_stderr(f"Attempt {attempt+1}: Failed to fetch package page for {Colorize.yellow(self.package)} from Anaconda.org (status code {resp.status_code})")
                    continue
            except requests.RequestException as e:
                Utils.print_stderr(f"Attempt {attempt+1}: Error fetching package page for {Colorize.yellow(self.package)} from Anaconda.org: {e}")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            p = soup.select_one("body > prex-root > prex-package-details > div > div > div > prex-package-overview > div > div.overview-content-cards > div.right-column > kendo-card > kendo-card-body > div:nth-child(1) > p:nth-child(2)")
            if p:
                text = p.get_text()
                # take first line and 150 max
                text = text.split("\n")[0].strip().replace("\t", " ").replace("\"", "").replace("'", "").strip(".")[:150]
                text = text[0].upper() + text[1:]  # Capitalize first letter
                if len(text) == 150:
                    text = text + "..."
                self.whatis = text
                a = soup.select_one("body > prex-root > prex-package-details > div > div > div > prex-package-overview > div > div.overview-content-cards > div.right-column > kendo-card > kendo-card-body > div:nth-child(6) > a")
                if a:
                    self.url = a['href'].strip()
                else:
                    self.url = url_page  # fallback to Anaconda page
                return True
            else:
                Utils.print_stderr(f"Failed to parse whatis for {Colorize.yellow(self.package)} from Anaconda.org")
                Utils.print_stderr(f"⚠️ The website layout may have changed. Please check the URL manually and update the {Colorize.yellow('soup.select_one')} selectors accordingly.")
                Utils.print_stderr(f"URL: {url_page}")
                Utils.print_stderr(f"Then rerun with {Colorize.yellow('-a')} {Colorize.yellow(self.package)}")
                return False
        
        Utils.print_stderr(f"⚠️ All attempts failed to fetch whatis/url for {Colorize.yellow(self.package)} from Anaconda.org")
        Utils.print_stderr(f"If you want to update the whatis/url later, please rerun with {Colorize.yellow('-a')} {Colorize.yellow(self.package)}")
        return False

    def update_versions(self, force: bool = False):
        """Query micromamba for package versions if source!=NA and store sorted."""
        if not force and not self.is_conda():
            return

        cmd = Config.get_search_command(self.package)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            # Extract versions from result["pkgs"]
            pkgs = data.get("result", {}).get("pkgs", [])
            raw_versions = [pkg.get("version") for pkg in pkgs if "version" in pkg]
            raw_channels = [pkg.get("channel") for pkg in pkgs if "channel" in pkg]
            raw_versions = list(set(raw_versions))  # Remove duplicates

            # Store sorted versions
            self.versions = self.version_order(raw_versions)
            if force and len(self.versions) != 0:
                self.source = raw_channels[0] if raw_channels else "NA"  # Ensure conda flag is set to channel if versions found

        except subprocess.CalledProcessError as e:
            Utils.print_stderr(f"Error running micromamba search for {self.package}: {e.stderr}")
        except json.JSONDecodeError as e:
            Utils.print_stderr(f"Error decoding JSON from micromamba search for {self.package}: {e}")

    def get_latest_version(self) -> Optional[str]:
        """Return the latest version available."""
        if self.versions and len(self.versions) > 0:
            return self.versions[0]
        return None

class PackageManager:
    """
    Stores and manages a collection of Package objects.
    """
    def __init__(self, tsv_path: str):
        self.tsv_path = tsv_path
        self.packages: Dict[str, Package] = {}
        if os.path.exists(tsv_path):
            self.load_from_tsv()
        else:
            Utils.print_stderr(f"TSV file {tsv_path} not found. Starting with an empty package database.")
            os.makedirs(os.path.dirname(tsv_path), exist_ok=True)
            self.update_local_packages()
            self.save_to_tsv(tsv_path)
        
    def update_package(self, pkg: Package):
        self.packages[pkg.package] = pkg
    
    def get_package(self, package_name: str) -> Optional[Package]:
        """
        Retrieve a package object by name
        """
        return self.packages.get(package_name, None)

    def add_entry_from_name(self, name: str) -> bool:
        """
        Create a Package from <package> string, fetch its info, and add to the database.
        Returns True if successful, False otherwise.
        """
        if name in self.packages:
            Utils.print_stderr(f"Package {Colorize.yellow(name)} already exists in the database. Updating info...")
            pkg = self.packages[name]
        else:
            pkg = Package.new_from_string(name)
        Utils.print_stderr(f"Fetching information for package {Colorize.yellow(name)} from Anaconda.org...")
        pkg.update_versions(force=True)
        if pkg.whatis == "":
            pkg.update_whatis_url()
        if pkg.source != "NA":
            self.update_package(pkg)
            return True
        else:
            Utils.print_stderr(f"❌ Package {Colorize.yellow(name)} not found in Anaconda repositories.")
            return False

    def load_from_tsv(self):
        """
        Load packages from a TSV file.
        Expected columns: package, tags (comma-separated), whatis, url, source (channel), optional versions
        """
        with open(self.tsv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                tags = [t.strip() for t in row.get("tags", "").split(",")] if row.get("tags") else []
                versions = [v.strip() for v in row.get("versions","").split(",")] if row.get("versions") else None
                pkg = Package(
                    package=row["package"],
                    tags=tags,
                    whatis=row.get("whatis", ""),
                    url=row.get("url", ""),
                    source=row.get("source", "NA")
                )
                pkg.versions = versions
                self.update_package(pkg)

    def save_to_tsv(self, path: str = None):
        """
        Save the current package data back to a TSV file.
        Includes the versions as a comma-separated string in a 'versions' column.
        Writes to a backup file first, then replaces the original.
        """
        if path is None:
            path = self.tsv_path

        backup_path = path + ".bak"
        fieldnames = ["package", "tags", "whatis", "url", "source", "versions"]

        # Write to backup first
        with open(backup_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, delimiter="\t", fieldnames=fieldnames)
            writer.writeheader()
            for pkg in self.packages.values():
                writer.writerow({
                    "package": pkg.package,
                    "tags": ",".join(pkg.tags),
                    "whatis": pkg.whatis,
                    "url": pkg.url,
                    "source": pkg.source,
                    "versions": ",".join(pkg.versions) if pkg.versions else ""
                })

        # Replace the original TSV with backup
        shutil.move(backup_path, path)

    def fetch_all_online_versions(self):
        """
        Call add_versions() on all packages in the database.
        """
        for pkg in self.packages.values():
            if not pkg.is_local():
                Utils.print_stderr(f"Fetching versions for {Colorize.yellow(pkg.package)}...")
                pkg.update_versions()
                if pkg.whatis == "":
                    pkg.update_whatis_url()

    def get_local_package_names(self) -> List[str]:
        """
        Return a list of all local package names in the database.
        """
        return [pkg.package for pkg in self.packages.values() if pkg.is_local()]

    def update_local_packages(self):
        """
        Read build_scripts directory for local packages and add them to the database. It will overwrite existing source entries.
        """
        Utils.print_stderr("Updating local packages from build-scripts folder...")
        updated_packages = set()
        script_paths = os.listdir(Config.build_scripts_root)
        script_paths = sorted(script_paths)
        for script_name in script_paths:
            if script_name == "0-template":
                continue
            script_relative_path = os.path.join(Config.build_scripts_root, script_name)
            if not os.path.isdir(script_relative_path):
                continue

            versions = os.listdir(script_relative_path)
            versions = [v for v in versions if not (v.startswith("template") or v.endswith("_data"))]
            if len(versions) == 0:
                continue
            versions = Package.version_order(versions)
            
            # Test if version is a file or directory
            if os.path.isdir(os.path.join(script_relative_path, versions[0])):
                Utils.print_stderr(f"Processing reference data package: {script_name}")
                assembly_data_version = []
                for assembly_data in versions:
                    data_version = os.listdir(os.path.join(script_relative_path, assembly_data))
                    data_version = [v for v in data_version if not v.startswith("template")]
                    for dv in data_version:
                        assembly_data_version.append(f"{assembly_data}/{dv}")
                if len(assembly_data_version) == 0:
                    Utils.print_stderr(f"Warning: No valid data versions found for reference package {script_name}. Skipping.")
                    continue
                pkg = Package.new_from_string(script_name)
                pkg.versions = Package.version_order(assembly_data_version)
                pkg.whatis = f"Assembly {script_name} reference and index data"
                pkg.url = ""
                pkg.source = "ref"
                updated_packages.add(script_name)
            else:
                Utils.print_stderr(f"Processing executable package: {script_name}")
                updated_packages.add(script_name)

                pkg = Package.new_from_string(script_name)
                pkg.source = "local"
                pkg.versions = versions

                latest_version = versions[0]
                latest_version_path = os.path.join(script_relative_path, latest_version)
                #WHATIS example: #WHATIS:GRCh38 GENCODE GTF annotation
                latest_content = open(latest_version_path, "r").read()
                whatis_match = re.search(r"#WHATIS:(.*)", latest_content)
                if whatis_match:
                    pkg.whatis = whatis_match.group(1).strip()
                url_match = re.search(r"#URL:(.*)", latest_content)
                if url_match:
                    pkg.url = url_match.group(1).strip()
            self.update_package(pkg)
        
        # Remove local packages that are no longer present
        existing_local_packages = set(self.get_local_package_names())
        for pkg_name in existing_local_packages - updated_packages:
            Utils.print_stderr(f"Removing local package {Colorize.yellow(pkg_name)} from database as it is no longer present in build-scripts.")
            del self.packages[pkg_name]

    def install_conda(self, package_name: str, version: str) -> bool:
        """
        Install the package at the specified version using micromamba.
        """
        pkg = self.get_package(package_name)
        if pkg is None:
            Utils.print_stderr(f"❌ Package {Colorize.yellow(package_name)} not found in database.")
            return False
        if pkg.versions is None or version not in pkg.versions:
            Utils.print_stderr(f"❌ Version {Colorize.yellow(version)} of package {Colorize.yellow(package_name)} not found in database.")
            return False
    
        Utils.print_stderr(f"Installing {Colorize.yellow(package_name)}/{Colorize.yellow(version)} via micromamba...")
        cmd = Config.get_create_command(package_name, version)

        try:
            subprocess.run(cmd, check=True)
            Utils.print_stderr(f"✅ Package {Colorize.yellow(package_name)} version {Colorize.yellow(version)} installed successfully via micromamba.")

            template_path = os.path.join(Config.build_scripts_root, "apps-template")
            template_lua_path = template_path + ".lua"

            # Cat module files to modulefiles/<package>/<version>
            modulefile_dir = os.path.join(Config.apps_modulefiles_root, package_name)
            os.makedirs(modulefile_dir, exist_ok=True)
            modulefile_path = os.path.join(modulefile_dir, version)
            modulefile_lua_path = modulefile_path + ".lua"

            with open(template_path, "r", encoding="utf-8") as f_in, \
                    open(modulefile_path, "w", encoding="utf-8") as f_out:
                template_content = f_in.read()
                # Replace placeholders
                whatis_text = pkg.whatis if pkg.whatis else "Loads $app_name version $app_version"
                template_content = template_content.replace("${WHATIS}", whatis_text)
                help_text = f"WEBSITE: {pkg.url}" if pkg.url else "No additional information available."
                template_content = template_content.replace("${HELP}", help_text)
                f_out.write(template_content)
            with open(template_lua_path, "r", encoding="utf-8") as f_in, \
                    open(modulefile_lua_path, "w", encoding="utf-8") as f_out:
                template_content = f_in.read()
                # Replace placeholders
                whatis_text = pkg.whatis if pkg.whatis else "\"Loads \" .. app_name .. \" version \" .. app_version"
                template_content = template_content.replace("${WHATIS}", whatis_text)
                help_text = f"WEBSITE: {pkg.url}" if pkg.url else "No additional information available."
                template_content = template_content.replace("${HELP}", help_text)
                f_out.write(template_content)

            Utils.print_stderr(f"📜 Module files created at {modulefile_path} and {modulefile_lua_path}")
            return True
        except subprocess.CalledProcessError as e:
            Utils.print_stderr(f"❌ Error installing {package_name} version {version} via micromamba: {e.stderr}")
            return False

    def get_local_dependencies(self, package_name: str, version: str) -> List[tuple[str, Optional[str]]]:
        """
        Parse the local build script for dependencies.
        Returns a list of (dependency_name, dependency_version) tuples.
        """
        dependencies = []
        script_path = os.path.join(Config.build_scripts_root, package_name, version)
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Local build script for {package_name}/{version} not found.")

        script_content = open(script_path, "r", encoding="utf-8").read()
        for line in script_content.split("\n"):
            if line.startswith("#DEPENDENCY:"):
                dep = line.split(":", 1)[1].strip()
                dep_name, dep_version = self.get_package_version(dep)
                dependencies.append((dep_name, dep_version))
        return dependencies

    def install_local(self, package_name: str, version: str) -> bool:
        """
        Install the package from local build-scripts.
        """
        script_path = os.path.join(Config.build_scripts_root, package_name, version)
        if not os.path.exists(script_path):
            Utils.print_stderr(f"Local build script for {Colorize.yellow(package_name)}/{Colorize.yellow(version)} not found.")
            return False

        Utils.print_stderr(f"Installing {Colorize.yellow(package_name)}/{Colorize.yellow(version)} from local build script...")

        try:
            dependencies = self.get_local_dependencies(package_name, version)
        except Exception as e:
            Utils.print_stderr(f"❌ Error parsing dependencies for {Colorize.yellow(package_name)}/{Colorize.yellow(version)}: {e}")
            return False

        for dep_name, dep_version in dependencies:
            Utils.print_stderr(f"Installing dependency {Colorize.yellow(dep_name)}/{Colorize.yellow(dep_version if dep_version else 'latest')} for {Colorize.yellow(package_name)}/{Colorize.yellow(version)}...")
            success = self.install_package(dep_name, dep_version)
            if not success:
                Utils.print_stderr(f"❌ Failed to install dependency {Colorize.yellow(dep_name)}/{Colorize.yellow(dep_version if dep_version else 'latest')} for {Colorize.yellow(package_name)}/{Colorize.yellow(version)}.")
                return False

        subprocess_cmd = ["bash", script_path, "-i"]
        exit_code = subprocess.call(subprocess_cmd)
        if exit_code == 0:
            Utils.print_stderr(f"✅ Package {package_name} version {version} installed successfully from local build script.")
            return True
        else:
            Utils.print_stderr(f"❌ Error installing {package_name} version {version} from local build script.")
            return False

    def install_package(self, package_name: str, version: Optional[str]) -> bool:
        """
        Install the package at the specified version using micromamba.
        """
        pkg = self.get_package(package_name)
        if pkg is None or pkg.versions is None:
            Utils.print_stderr(f"❌ Package {Colorize.yellow(package_name)} not found in database.")
            return False

        if version is None:
            version = pkg.get_latest_version()
            if version is None:
                Utils.print_stderr(f"❌ No version specified and no versions available for package {Colorize.yellow(package_name)}.")
                return False
        
        if pkg.is_ref():
            modulefile_path = os.path.join(Config.ref_modulefiles_root, package_name, version)
        else:
            modulefile_path = os.path.join(Config.apps_modulefiles_root, package_name, version)
        if os.path.exists(modulefile_path):
            Utils.print_stderr(f"Module file for {Colorize.yellow(package_name)}/{Colorize.yellow(version)} already exists at {modulefile_path}. Skipping installation.")
            return True
        
        if version not in pkg.versions:
            if version.endswith("*"):
                prefix = version[:-1]
                matched_versions = [v for v in pkg.versions if v.startswith(prefix)]
                if matched_versions:
                    version = matched_versions[0]
                    Utils.print_stderr(f"Using version {Colorize.yellow(version)} for package {Colorize.yellow(package_name)} matching prefix {Colorize.yellow(prefix)}*")
                else:
                    Utils.print_stderr(f"❌ No versions found matching prefix {Colorize.yellow(prefix)}* for package {Colorize.yellow(package_name)}.")
                    return False
    
        if os.path.exists(os.path.join(Config.apps_root, package_name, version)):
            Utils.print_stderr(f"Package {Colorize.yellow(package_name)}/{Colorize.yellow(version)} is already installed.")
            return True
        
        if pkg.is_local():
            result = self.install_local(package_name, version)
        elif pkg.is_conda():
            result = self.install_conda(package_name, version)
        else:
            Utils.print_stderr(f"❌ Unknown package type for {Colorize.yellow(package_name)}.")
            return False

        if not result:
            self.delete(package_name, version)
            return False
        
        return True

    def delete(self, package_name: str, version: str) -> bool:
        """
        Remove the installed package at the specified version.
        """
        is_ref = False
        pkg = self.get_package(package_name)
        if pkg is None:
            is_ref = "/" in version
        else:
            is_ref = pkg.is_ref()

        if is_ref:
            install_path = os.path.join(Config.ref_root, package_name, version)
            package_path = os.path.join(Config.ref_root, package_name)
            modulefile_path = os.path.join(Config.ref_modulefiles_root, package_name, version)
            modulefile_package_path = os.path.join(Config.ref_modulefiles_root, package_name)
        else:
            install_path = os.path.join(Config.apps_root, package_name, version)
            package_path = os.path.join(Config.apps_root, package_name)
            modulefile_path = os.path.join(Config.apps_modulefiles_root, package_name, version)
            modulefile_package_path = os.path.join(Config.apps_modulefiles_root, package_name)
        
        modulefile_lua_path = modulefile_path + ".lua"
        try:
            Utils.print_stderr(f"Removing {Colorize.yellow(package_name)}/{Colorize.yellow(version)}...")
            if os.path.exists(install_path):
                shutil.rmtree(install_path)
            Utils.rmdir_until_not_empty(os.path.dirname(install_path))

            if os.path.exists(modulefile_path):
                os.remove(modulefile_path)
            if os.path.exists(modulefile_lua_path):
                os.remove(modulefile_lua_path)
            Utils.rmdir_until_not_empty(modulefile_package_path)

            return True
        except Exception as e:
            Utils.print_stderr(f"❌ Error cleaning package {Colorize.yellow(self.package)}/{Colorize.yellow(version)}: {e}")
            return False

    def is_package_installed(self, package_name: str, version: str) -> bool:
        """
        Check if the package at the specified version is installed.
        """
        pkg = self.get_package(package_name)
        is_ref = False
        if pkg is None:
            is_ref = "/" in version
        else:
            is_ref = pkg.is_ref()

        if is_ref:
            install_path = os.path.join(Config.ref_root, package_name, version)
        else:
            install_path = os.path.join(Config.apps_root, package_name, version)
        return os.path.exists(install_path)

    def print_info(self, package_name: str):
        """
        Print detailed information about the package.
        """
        pkg = self.get_package(package_name)
        if pkg is None:
            Utils.print_stderr(f"Package {Colorize.yellow(package_name)} not found in database.")
            return

        print(f"Package: {pkg.package}")
        print(f"Tags: {', '.join(pkg.tags) if pkg.tags else 'N/A'}")
        print(f"WHATIS: {pkg.whatis if pkg.whatis else 'N/A'}")
        print(f"URL: {pkg.url if pkg.url else 'N/A'}")
        print(f"Source: {pkg.source}")
        if pkg.versions:
            print(f"Available Versions: {', '.join(pkg.versions)}")
        else:
            print("Available Versions: N/A")

    def search_term(self, term: str) -> List[Package]:
        """
        Search for packages matching the term in name or tags or WHATIS.
        Returns a list of matching Package objects.
        """
        matches = []
        term_lower = term.lower()
        for pkg in self.packages.values():
            if term_lower in pkg.package.lower() or any(term_lower in tag.lower() for tag in pkg.tags) or term_lower in pkg.whatis.lower():
                matches.append(pkg)
        return matches

    def get_package_version(self, input_str: str) -> tuple[str, str]:
        """
        Given <package>/<version> or <package>, return the matched package/version.
        Raise ValueError on failure.
        """
        if "/" in input_str:
            package_name, version = input_str.split("/", 1)
        else:
            package_name = input_str
            version = None
        
        pkg = self.get_package(package_name)
        if pkg is None:
            pkg = Package.new_from_string(package_name)
            pkg.update_versions(force=True)
            pkg.update_whatis_url()
            if pkg.source == "NA":
                raise ValueError(f"Package {package_name} not found.")
            self.update_package(pkg)
            self.save_to_tsv()

        if version is None:
            latest_version = pkg.get_latest_version()
            if latest_version is None:
                raise ValueError(f"No versions found for package {package_name}.")
            return package_name, latest_version
        else:
            if version in pkg.versions:
                return package_name, version
            elif version.endswith("*"):
                prefix = version[:-1]
                matched_versions = [v for v in pkg.versions if v.startswith(prefix)]
                if matched_versions:
                    matched_version = matched_versions[0]
                    return package_name, matched_version
                else:
                    raise ValueError(f"No versions found for package {package_name} with prefix {prefix}.")
            else:
                raise ValueError(f"Version {version} not found for package {package_name}.")
    
    def print_package_version(self, input_str: str):
        """
        Given <package>/<version> or <package>, print the matched package/version to STDOUT.
        Prompt messages to STDERR.
        Exit with code 0 on success, 1 on failure.
        """
        try:
            package_name, version = self.get_package_version(input_str)
            print(f"{package_name}/{version}")
            sys.exit(0)
        except ValueError as e:
            Utils.print_stderr(str(e))
            sys.exit(1)

    def print_dependencies(self, package_version_str: str):
        """
        Print the dependencies of the specified package/version to STDOUT.
        """
        if "/" in package_version_str:
            package_name, version = package_version_str.split("/", 1)
        else:
            Utils.print_stderr(f"❌ Invalid input {Colorize.yellow(package_version_str)}. Expected format: <package>/<version>.")
            sys.exit(1)
        try:
            dependencies = self.get_local_dependencies(package_name, version)
            if not dependencies:
                sys.exit(0)  # No dependencies to print
            for dep_name, dep_version in dependencies:
                if dep_version:
                    print(f"{dep_name}/{dep_version}")
                else:
                    print(f"{dep_name}")
            sys.exit(0)
        except Exception as e:
            Utils.print_stderr(f"❌ Error retrieving dependencies for {Colorize.yellow(package_name)}/{Colorize.yellow(version)}: {e}")
            Utils.print_stderr(f"You may need to run {Colorize.yellow('./manager.py -u')} to update the local package database.")
            sys.exit(1)

    def sort_packages(self):
        """
        Sort the internal package dictionary by package name.
        """
        local_packages = []
        conda_packages = []
        for pkg in self.packages.values():
            if pkg.is_local():
                local_packages.append(pkg)
            else:
                conda_packages.append(pkg)
        local_packages.sort(key=lambda p: p.package.lower())
        conda_packages.sort(key=lambda p: p.package.lower())
        sorted_packages = local_packages + conda_packages
        self.packages = {pkg.package: pkg for pkg in sorted_packages}
    
    def list_packages(self):
        """
        List all packages in the database.
        """
        self.sort_packages()
        max_len = max(len(pkg.package) for pkg in self.packages.values()) if self.packages else 10
        for pkg in self.packages.values():
            print(f"{Colorize.yellow(pkg.package.ljust(max_len))}: {pkg.whatis}")

# Example usage
if __name__ == "__main__":
    main()
