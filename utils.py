#!/usr/bin/env python3

import os
import subprocess
import time
import re

class Colorize:
    def red(text):
        return f'\033[91m{text}\033[0m'
    def blue(text):
        return f'\033[94m{text}\033[0m'
    def yellow(text):
        return f'\033[93m{text}\033[0m'
    def green(text):
        return f'\033[92m{text}\033[0m'

def main():
    if not os.path.exists('build-scripts'):
        print(f'{Colorize.red("Error")}: {Colorize.blue("build-scripts")} directory not found')
        print('Please run this script in the modules directory')
        exit(1)

    import argparse
    parser = argparse.ArgumentParser(description='Utility script for modules overview and batch operations')
    parser.add_argument('-l', '--list-all', action='store_true', help='list all the app/versions and their status')
    parser.add_argument('-lw', '--list-whatis', action='store_true', help='list the whatis of all apps')
    parser.add_argument('-lm', '--list-module', dest='name', help='list all the versions and dependencies from given name')
    parser.add_argument('-lu', '--list-upgradable', action='store_true', help='list upgradable apps')
    parser.add_argument('-ln', '--list-newest', action='store_true', help='list apps with newer version (even if not installed)')
    parser.add_argument('-li', '--list-installed', action='store_true', help='list installed apps with versions')
    parser.add_argument('-i', '--install-newest', action='store_true', help='install newest version of each app')
    parser.add_argument('-d', '--delete-all', action='store_true', help='delete all installed apps')
    args = parser.parse_args()

    if args.list_all:
        list_modules()
    elif args.list_whatis:
        list_modules(include_whatis=True, include_versions=False, include_dependencies=False)
    elif args.name is not None:
        list_dep(args.name)
    elif args.list_upgradable:
        list_upgradable()
    elif args.list_newest:
        list_newest()
    elif args.list_installed:
        list_modules(include_whatis=True, include_versions=True, include_dependencies=False, installed_only=True)
    elif args.install_newest:
        install_newest()
    elif args.delete_all:
        delete_all()
    else:
        list_modules(include_whatis=True, include_versions=True, include_dependencies=False)

def get_status()-> dict:
    """
    Get the status of the apps and versions in the build-scripts directory

    Returns:
        dict: A nested dictionary containing the status of the apps and versions (True if installed, False if not)
    """
    status = {}

    for app in os.listdir('build-scripts'):
        if os.path.isdir(os.path.join('build-scripts', app)) and app != "0-template":
            status[app] = {}
            for version in os.listdir(os.path.join('build-scripts', app)):
                if os.access(os.path.join('build-scripts', app, version), os.X_OK):
                    status[app][version] = True if os.path.isdir(os.path.join('apps', app, version)) else False

    return status

def parse_version_key(version: str):
    """
    Parse the version key from the version string

    Args:
        version (str): The version string

    Returns:
        tuple: A tuple containing the major, minor, and patch versions
    """
    components = re.findall(r'(\d+)|([a-zA-Z]+)', version)
    # Example breakdown:
    # "1.10.2b" -> [('1', ''), ('10', ''), ('2', ''), ('', 'b')]
    # "2025c"   -> [('2025', ''), ('', 'c')]
    # "3.0"     -> [('3', ''), ('0', '')]
    parsed_key = []
    for num_str, alpha_str in components:
        if num_str:
            # Append numbers as integers for correct numerical comparison
            parsed_key.append(int(num_str))
        elif alpha_str:
            # Append letter sequences as strings for lexicographical comparison
            parsed_key.append(alpha_str)

    return tuple(parsed_key)

def version_order(versions: list, descending=True) -> list:
    """
    Order the versions in the list (descending by default)
    """
    return sorted(versions, key=parse_version_key, reverse=descending)

def get_whatis(app: str, version: str) -> str:
    """
    Get the whatis of the app and version

    Args:
        app (str): The app name
        version (str): The version of the app

    Returns:
        str: The whatis of the app and version
    """
    with open(f'build-scripts/{app}/{version}') as f:
        for line in f:
            if line.startswith('#WHATIS'):
                return line.strip().split(":")[1]
    return None

def get_dependencies(app: str, version: str) -> list:
    """
    Get the dependencies of the app and version

    Args:
        app (str): The app name
        version (str): The version of the app

    Returns:
        list: A list of dependencies
    """
    dependencies = []
    with open(f'build-scripts/{app}/{version}') as f:
        for line in f:
            if line.startswith('#DEPENDENCY'):
                name, version = line.strip().split(":")[1].split("/")
                dependencies.append(resolve_app_version(name, version))
    return dependencies

def resolve_app_version(app: str, version_match: str) -> (str, str):
    """
    Resolve the app and version from the app and version_match

    Args:
        app (str): The app name
        version_match (str): The version match

    Returns:
        (str, str): The app and version
    """
    if "*" not in version_match:
        return app, version_match

    version_match = version_match.replace("*", "")
    versions = version_order(os.listdir(f'build-scripts/{app}'))
    for version in versions:
        if version.startswith(version_match):
            return app, version

    return app, None

def get_dependencies_name(app: str, version: str) -> list:
    """
    Get the dependencies of the app and version

    Args:
        app (str): The app name
        version (str): The version of the app

    Returns:
        list: A list of dependencies (only the name)
    """
    dependencies = []
    with open(f'build-scripts/{app}/{version}') as f:
        for line in f:
            if line.startswith('#DEPENDENCY'):
                dependencies.append(line.strip().split(":")[1].split("/")[0])
    return dependencies

def resolve_dependencies(apps: list, dependencies: dict) -> list:
    """
    Resolve the dependencies of the apps

    Args:
        apps (list): A list of apps
        dependencies (dict): A dictionary of dependencies

    Returns:
        list: A list of apps in the order of installation
    """
    resolved = []
    seen = set()

    def visit(app):
        # This recursive function will make sure that the dependencies are installed first
        if app not in seen:
            seen.add(app)
            for dep in dependencies.get(app, []):
                visit(dep)
            resolved.append(app) # app with no dependency will add first
    
    for app in apps:
        visit(app)
    
    return resolved

def print_status(status: dict, include_whatis: bool = False, include_versions: bool = True, include_dependencies: bool = True, installed_only: bool = False):
    """
    Print the status of the apps and versions
    """

    # get length of the longest app name and version for formatting
    max_app_len = len(max(status.keys(), key=len)) if status else 0
    max_version_len = len(max([version for app in status for version in status[app]], key=len)) if status else 0
    # print the header
    print('App'.ljust(max_app_len), f' ({Colorize.blue("*")}) installed ( ) not installed {Colorize.blue("D")} dependencies')
    # each line is an app
    for app in sorted(status.keys()):
        if installed_only and not any(status[app].values()): # skip apps with no installed versions
            continue

        print(f'{Colorize.yellow(app.ljust(max_app_len))}:', end=' ')
        if include_whatis:
            whatis = get_whatis(app, next(iter(status[app].keys())))
            if whatis:
                print(whatis)
            else:
                print()
        if include_versions:
            if include_whatis and whatis:
                print(' '*max_app_len, end='  ')
            # order the versions
            if installed_only:
                versions = version_order([version for version in status[app] if status[app][version]])
            else:
                versions = version_order(status[app].keys())
            # each column is a version
            for version in versions:
                print(f'{("("+Colorize.blue("*")+")") if status[app][version] else "( )"} {version.ljust(max_version_len)}', end='  ')
            print()
            # print dependencies
            # dependencies = get_dependencies_name(app, versions[0])
            if include_dependencies:
                dependency_versions = get_dependencies(app, versions[0])
                dependencies = [f'{Colorize.yellow(dep[0])}/{dep[1]}' for dep in dependency_versions]
                if dependencies:
                    print(' '*max_app_len, f'     └─ {Colorize.blue("D")}', ", ".join(dependencies))

def list_dep(app: str):
    """
    List the dependencies of the app
    """
    status = get_status()
    if "*" in app:
        import re
        re_app = re.compile("^" + app.replace("*", ".*") + "$")
        apps = [app for app in status if re_app.match(app)]
        status = {app: status[app] for app in apps}
    else:
        if app not in status:
            print(f'{Colorize.red("Error")}: {app} not found')
            exit(1)
        status = {app: status[app] for app in [app]}

    print_status(status, include_whatis=True, include_versions=True, include_dependencies=True)

#region All
def list_modules(include_whatis: bool = False, include_versions: bool = True, include_dependencies: bool = True, installed_only: bool = False):
    """
    Check the version diff between build-scripts and installed apps
    """
    status = get_status()

    print_status(status, include_whatis, include_versions, include_dependencies, installed_only)

def delete_all():
    """
    Delete all versions of each installed app listed in build-scripts
    """
    status = get_status()
    apps = status.keys()
    versions_str = [
        f'{Colorize.yellow(app)}/{version}' 
            for app in apps 
                for version in status[app] 
                    if status[app][version]
    ]

    if not versions_str:
        print('No apps to delete')
        exit()

    print('Following apps will be deleted:')
    len_longest = len(max(versions_str, key=len)) if versions_str else 0

    # 4 columns
    counter = 0
    for version in versions_str:
        print(version.ljust(len_longest), end='  ')
        counter += 1
        if counter % 4 == 0:
            print()

    print("\nAre you sure? (y/n)", end=': ')
    reply = input()
    if reply.lower() != 'y':
        print('Aborted')
        exit()
    
    success_apps = []
    failed_apps = []
    for app in apps:
        versions = version_order(status[app].keys())
        for version in versions:
            if status[app][version]: # if installed
                print(f'Deleting {app}/{version} ... ', end='', flush=True)
                result = subprocess.run(
                    [f'./build-scripts/{app}/{version}', '-d'],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    print(Colorize.blue('Success'))
                    success_apps.append(f'{Colorize.yellow(app)}/{version}')
                else:
                    print(Colorize.red('Failed'))
                    failed_apps.append(f'{Colorize.yellow(app)}/{version}')
    
    if success_apps:
        print('Deleted:', ", ".join(sorted(success_apps)))
    if failed_apps:
        print('Failed to delete:', ", ".join(sorted(failed_apps)))
#endregion

def get_newer_versions(status: dict) -> dict:
    """
    Get the apps and versions that have a newer version in build-scripts

    Args:
        status (dict): The status of the apps and versions

    Returns:
        dict: A dictionary key is app value is the newest version (only if the newest version is not installed)
    """
    newer_versions = {}
    for app in status.keys():
        versions = version_order(status[app].keys())
        if not status[app][versions[0]]:
            newer_versions[app] = versions[0]
    return newer_versions

def list_newest():
    """
    List the apps that have a newer version in build-scripts
    """
    status = get_status()
    newer_versions = get_newer_versions(status)
    apps_no_newer = [app for app in status if app not in newer_versions]
    len_app = len(max(newer_versions.keys(), key=len)) if newer_versions else 0
    
    print('Apps with newer version:')
    for app in sorted(newer_versions.keys()):
        print(f'{app.ljust(len_app)}: {newer_versions[app]}')
    print('\nApps already have the newest version:')
    print(", ".join(sorted(apps_no_newer)))

def install_newest():
    """
    Install the newest version of each app in build-scripts
    """
    status = get_status()
    newer_versions = get_newer_versions(status)
    if not newer_versions:
        print('All apps are up-to-date')
        exit()
    newer_apps_sorted = sorted(newer_versions.keys())
    len_app = len(max(newer_apps_sorted, key=len)) if newer_apps_sorted else 0
    len_number = len(str(len(newer_apps_sorted)))

    print('Following apps have newer version available:')
    for i, app in enumerate(newer_apps_sorted):
        print(f'{Colorize.blue(str(i+1).rjust(len_number))}) {app.ljust(len_app)}: {newer_versions[app]}')

    print(f'Select the apps to install ({Colorize.blue(",")} separated)')
    print(f'Or {Colorize.blue("a")}/{Colorize.blue("y")} for all, {Colorize.red("n")} for none', end=': ')
    reply = input()
    if reply.lower() in ['a', 'y']:
        selected_apps = newer_apps_sorted
    elif reply.lower() in ['n', '']:
        print('Aborted')
        exit()
    else:
        try:
            selected_apps = [newer_apps_sorted[int(i.strip())-1] for i in reply.split(',')]
        except:
            print(Colorize.red('Invalid input'))
            exit(1)
    
    dep_dict = {} # key is app, value is 
    # Check dependencies. Put dependencies to top.
    for app in selected_apps:
        dep_dict[app] = get_dependencies_name(app, newer_versions[app])
    selected_apps_sorted = resolve_dependencies(selected_apps, dep_dict)
    # remove app not in selected_apps
    selected_apps_sorted = [app for app in selected_apps_sorted if app in selected_apps]

    success_apps = []
    failed_apps = []
    for app in selected_apps_sorted:
        print(f'Installing {Colorize.yellow(app)}/{newer_versions[app]} ... ', end='', flush=True)

        result = subprocess.run(
            [f'./build-scripts/{app}/{newer_versions[app]}', '-i'],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print(Colorize.blue('Success'))
            success_apps.append(app)
        else:
            print(Colorize.red('Failed'))
            failed_apps.append(app)
    if success_apps:
        print('Installed:', ", ".join(sorted(success_apps)))
    if failed_apps:
        print('Failed to install:', ", ".join(sorted(failed_apps)))

def list_upgradable():
    """
    List the apps that have an upgradable version
    """
    status = get_status()
    status = {app: versions for app, versions in status.items() if any(versions.values())}
    newer_versions = get_newer_versions(status)
    upgradable_apps = {app: version for app, version in newer_versions.items() if app in status}
    len_app = len(max(upgradable_apps.keys(), key=len)) if upgradable_apps else 0

    print('Upgradable apps:')
    for app in sorted(upgradable_apps.keys()):
        print(f'{app.ljust(len_app)}: {upgradable_apps[app]}')

if __name__ == '__main__':
    main()
