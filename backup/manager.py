#!/usr/bin/env python3
import os
import platform
import urllib.request
import stat
import subprocess
import json
import re
import csv
import shutil
import argparse
from typing import Dict, List, Optional

# External libraries
import requests
from bs4 import BeautifulSoup

class Config:
    # TSV fields: package | tags | whatis | url | conda | versions
    metadata_root = "./metadata"          # Default metadata root
    build_scripts_path = "./build-scripts"  # Default build scripts path
    apps_path = "./apps"                    # Default installation path
    modulefiles_path = "./modulefiles"      # Default modulefiles path
    micromamba_root = "./conda"             # Default micromamba root
    tsv_path = os.path.join(metadata_root, "packages.tsv")  # Default TSV path
    
def main():
    parser = argparse.ArgumentParser(description="Package Manager")
    parser.add_argument("-i", "--install", type=str, help="<package>/<version> to install")
    parser.add_argument("-u", "--update", action="store_true", help="Update package versions in the database")
    parser.add_argument("-a", "--add", type=str, help="Add a new <package> to the database")
    parser.add_argument("-s", "--search", type=str, help="<package> to search (not implemented)")
    parser.add_argument("-l", "--list", action="store_true", help="List all packages (not implemented)")
    parser.add_argument("-li", "--list-installed", action="store_true", help="List installed packages (not implemented)")
    parser.add_argument("-d", "--delete", type=str, help="<package>/<version> to delete (wildcard *) (not implemented)")
    args = parser.parse_args()

    pm = PackageManager(Config.tsv_path)

    if args.update:
        pm.fetch_all_versions()
        pm.save_to_tsv()
        print("Package versions updated.")
    elif args.add:
        success = pm.add_entry_from_name(args.add)
        if success:
            pm.save_to_tsv()
    elif args.install:
        success = pm.install_package(args.install)
        if success:
            print(f"Successfully installed {args.install}.")
        else:
            print(f"Failed to install {args.install}.")
    elif args.delete:
        print("Delete functionality not implemented yet.")

class Package:
    # Class static variables
    apps_path = Config.apps_path  # default installation path
    build_scripts_path = Config.build_scripts_path  # default build scripts path
    modulefiles_path = Config.modulefiles_path  # default modulefiles path
    micromamba_root = Config.micromamba_root  # default root for micromamba search

    def __init__(self, package: str, tags: List[str], whatis: str, url: str, conda: str):
        self.package = package
        self.tags = tags
        self.whatis = whatis
        self.url = url
        self.conda = conda  # conda channel or NA
        self.versions: Optional[List[str]] = None  # unsorted versions

    def __repr__(self):
        return (f"Package(package={self.package!r}, tags={self.tags!r}, "
                f"whatis={self.whatis!r}, url={self.url!r}, conda={self.conda!r}, "
                f"versions={self.versions})")

    @classmethod
    def get_micromamba_path(cls, version: str = None) -> str:
        """Download micromamba if missing and return its path."""
        os.makedirs(cls.micromamba_root, exist_ok=True)
        micromamba_path = os.path.join(cls.micromamba_root, "micromamba")

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

        print(f"Downloading micromamba from {release_url} ...")
        urllib.request.urlretrieve(release_url, micromamba_path)

        # Make executable
        st = os.stat(micromamba_path)
        os.chmod(micromamba_path, st.st_mode | stat.S_IEXEC)
        print(f"Micromamba downloaded and made executable at {micromamba_path}")

        return micromamba_path

    @staticmethod
    def new_from_string(data_str: str) -> 'Package':
        """
        Create a Package object from <package>/<version> string.
        """
        parts = data_str.split("/")
        package = parts[0]
        tags = []
        whatis = ""
        url = ""
        conda = "NA"

        return Package(package, tags, whatis, url, conda)

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

    def update_whatis_url(self) -> bool:
        """Fetch whatis and url from Anaconda.org if conda!=NA."""
        if self.conda == "NA":
            return True  # nothing to do

        url_page = f"https://anaconda.org/{self.conda}/{self.package}"
        resp = requests.get(url_page)
        if resp.status_code != 200:
            print(f"Failed to fetch package page for {self.package} from Anaconda.org")
            return False
        soup = BeautifulSoup(resp.text, 'html.parser')

        p = soup.select_one("body > div.container > div:nth-child(2) > div > div:nth-child(2) > div > p")
        if p:
            text = p.get_text(strip=True)
            # take first sentence (split by . or ! or ?)
            self.whatis = text.split(".")[0].strip() + "."
        else:
            print(f"Failed to parse whatis for {self.package} from Anaconda.org")
        
        a = soup.select_one("body > div.container > div:nth-child(2) > div > div:nth-child(4) > div > div:nth-child(1) > ul > li:nth-child(2) > a")
        if a:
            self.url = a['href'].strip()
        else:
            print(f"Failed to parse URL for {self.package} from Anaconda.org")
            self.url = url_page  # fallback to Anaconda page
        return True

    def update_versions(self, force: bool = False):
        """Query micromamba for package versions if conda!=NA and store sorted."""
        if not force and self.conda == "NA":
            self.versions = None
            return

        micromamba_path = self.get_micromamba_path()
        cmd = [
            micromamba_path,
            "search",
            "-r", self.micromamba_root,
            "-c", "conda-forge", "-c", "bioconda",
            "--json",
            self.package
        ]

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
                self.conda = raw_channels[0] if raw_channels else "NA"  # Ensure conda flag is set to channel if versions found

        except subprocess.CalledProcessError as e:
            print(f"Error running micromamba search for {self.package}: {e.stderr}")
            self.versions = None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from micromamba search for {self.package}: {e}")
            self.versions = None

    def install(self, version: str) -> bool:
        """
        Install the package at the specified version using micromamba.
        """
        if self.versions is None or version not in self.versions:
            print(f"Version {version} of package {self.package} not found.")
            return False
    
        print(f"Installing {self.package} version {version} via micromamba...")

        micromamba_path = self.get_micromamba_path()
        cmd = [
            micromamba_path,
            "create",
            "-r", self.micromamba_root,
            "-c", "conda-forge", "-c", "bioconda",
            "-p", os.path.join(self.apps_path, self.package, version),
            f"{self.package}={version}",
            "-q", "-y"
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"Package {self.package} version {version} installed successfully.")

            template_path = os.path.join(self.build_scripts_path, "template")
            template_lua_path = template_path + ".lua"

            # Cat module files to modulefiles_path/<package>/<version>
            modulefile_dir = os.path.join(self.modulefiles_path, self.package)
            os.makedirs(modulefile_dir, exist_ok=True)
            modulefile_path = os.path.join(modulefile_dir, version)
            modulefile_lua_path = modulefile_path + ".lua"

            with open(template_path, "r", encoding="utf-8") as f_in, \
                 open(modulefile_path, "w", encoding="utf-8") as f_out:
                f_out.write(f_in.read())
            with open(template_lua_path, "r", encoding="utf-8") as f_in, \
                 open(modulefile_lua_path, "w", encoding="utf-8") as f_out:
                f_out.write(f_in.read())

            print(f"Module files created at {modulefile_path} and {modulefile_lua_path}")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error installing {self.package} version {version}: {e.stderr}")
            return False

class PackageManager:
    """
    Stores and manages a collection of Package objects.
    """
    def __init__(self, tsv_path: str):
        self.tsv_path = tsv_path
        self.packages: Dict[str, Package] = {}
        if os.path.exists(tsv_path):
            self.load_from_tsv(tsv_path)
        else:
            print(f"TSV file {tsv_path} not found. Starting with an empty package database.")
            os.makedirs(os.path.dirname(tsv_path), exist_ok=True)
            self.save_to_tsv(tsv_path)
        
    def add_package(self, pkg: Package):
        self.packages[pkg.package] = pkg
    
    def add_entry_from_name(self, name: str) -> bool:
        """
        Create a Package from <package> string, fetch its info, and add to the database.
        Returns True if successful, False otherwise.
        """
        if name in self.packages:
            print(f"Package {name} already exists in the database. Updating info...")
            pkg = self.packages[name]
        else:
            pkg = Package.new_from_string(name)
        print(f"Fetching information for package {name}...")
        pkg.update_versions(force=True)
        pkg.update_whatis_url()
        if pkg.conda != "NA":
            self.add_package(pkg)
            return True
        else:
            print(f"Package {name} not found in Anaconda repositories. Please add it manually.")
            return False

    def load_from_tsv(self, tsv_path: str):
        """
        Load packages from a TSV file.
        Expected columns: package, tags (comma-separated), whatis, url, conda (channel), optional versions
        """
        with open(tsv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                tags = [t.strip() for t in row.get("tags", "").split(",")] if row.get("tags") else []
                versions = [v.strip() for v in row.get("versions","").split(",")] if row.get("versions") else None
                pkg = Package(
                    package=row["package"],
                    tags=tags,
                    whatis=row.get("whatis", ""),
                    url=row.get("url", ""),
                    conda=row.get("conda", "NA")
                )
                pkg.versions = versions
                self.add_package(pkg)

    def save_to_tsv(self, path: str = None):
        """
        Save the current package data back to a TSV file.
        Includes the versions as a comma-separated string in a 'versions' column.
        Writes to a backup file first, then replaces the original.
        """
        if path is None:
            path = self.tsv_path

        backup_path = path + ".bak"
        fieldnames = ["package", "tags", "whatis", "url", "conda", "versions"]

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
                    "conda": pkg.conda,
                    "versions": ",".join(pkg.versions) if pkg.versions else ""
                })

        # Replace the original TSV with backup
        shutil.move(backup_path, path)

    def fetch_all_versions(self):
        """
        Call add_versions() on all packages that have conda!=NA
        """
        for pkg in self.packages.values():
            if pkg.conda != "NA":
                print(f"Fetching versions for {pkg.package}...")
                pkg.update_versions()
                if pkg.whatis == "":
                    pkg.update_whatis_url()

    def get_package(self, package_name: str) -> Package | None:
        """
        Retrieve a package object by name
        """
        return self.packages.get(package_name, None)

    def install_package(self, package_str: str) -> bool:
        """
        Install a package given a <package>/<version> string.
        """
        name, version = package_str.split("/")
        pkg = self.get_package(name)
        if pkg is None:
            print(f"Package {name} not found in database. Attempting to add...")
            if self.add_entry_from_name(name):
                pkg = self.get_package(name)
                self.save_to_tsv()
            else:
                return False
        result = pkg.install(version)
        
        return result

# Example usage
if __name__ == "__main__":
    main()
