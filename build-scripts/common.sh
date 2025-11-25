#!/bin/bash

# -E traps ERR in functions and subshells
# -e exit on error
# -u exit on undefined variable
# -o pipefail exit if any command in a pipe fails
# -o errtrace inherit ERR trap in functions and subshells
set -Ee
set -o errtrace
cleanup_called=0

# Detect if this file is being sourced or executed.
# When sourced, we should not call `exit` (would exit the caller shell);
# when executed, calling `exit` is desired to terminate the script after cleanup.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    __COMMON_SOURCED=1
else
    __COMMON_SOURCED=0
fi
# This script contains common functions and variables for the build scripts.
# Must be sourced by other scripts.

#region VARIABLES
ncpu=${SLURM_CPUS_PER_TASK:-4} # number of cores to use when building from source
RED='\033[0;91m'    # Red      WARNING or ERROR
BLUE='\033[0;94m'   # Blue     Dependency or Modulefile Changes
YELLOW='\033[0;93m' # Yellow   App Name and/or Version
NC='\033[0m'        # No Color

modules_root="$PWD"
install_script_path="$(realpath --no-symlinks "$0")"
script_relative_path="${install_script_path#*/build-scripts/}" # build-scripts/name/version
# count number of slashed
slash_count=$(grep -o "/" <<< "$script_relative_path" | wc -l)
target=apps
if [ "$slash_count" = "2" ]; then
    target=ref
fi

app_name_version="${install_script_path#*/build-scripts/}" # name/version or ref/assembly/data-type/version
app_name="${app_name_version%/*}"  # name   or ref/assembly/data-type
version="${app_name_version##*/}"  # version
target_base_dir="${modules_root}/${target}/${app_name}"      # apps/name or ref/assembly/data-type
target_dir="${modules_root}/${target}/${app_name_version}"   # apps/name/version or ref/assembly/data-type/version
script_base_dir="${modules_root}/${target}_modulefiles/${app_name}"      # modulefiles/name or modulefiles/ref/assembly
script_path="${modules_root}/${target}_modulefiles/${app_name_version}"  # modulefiles/name/version or modulefiles/ref/assembly/data-type/version

tmp_dir="${modules_root}/tmp/${app_name_version}" # tmp directory
manager_script="${modules_root}/manager.py" # manager script path
dependencies=$("$manager_script" --print-dependencies "${app_name_version}")
#endregion

#region OPTION_FUNCTIONS
help_message() {
    echo "Usage: bash $0 [options]" 1>&2
    echo "Options:" 1>&2
    echo "  -i  Install the target module with dependencies." 1>&2
    echo "  -l  List the dependencies of the target module." 1>&2
    echo "  -d  Delete the target module." 1>&2
    echo "  -h  Help message." 1>&2
}

install() {
    # set traps for cleanup when installation ends or errors occur
    # For ERR and INT, run clean_up then either `exit` (if this script is executed)
    # or `return` (if this file was sourced) so we don't remain in any blocking `read`.
    trap 'echo "❌ Command failed: $BASH_COMMAND"; clean_up 1; if [[ $__COMMON_SOURCED -eq 0 ]]; then exit 1; else return 1; fi' ERR
    trap 'echo "🛑 CTRL+C detected. Exiting..."; clean_up 1; if [[ $__COMMON_SOURCED -eq 0 ]]; then exit 130; else return 130; fi' INT
    # EXIT trap should only perform cleanup; don't call exit/return here (it would re-trigger EXIT)
    trap 'clean_up 0' EXIT
    
    print_stderr "Installing the target module: ${YELLOW}${app_name_version}${NC}"
    print_stderr "🎯 Target directory: $target_dir"
    print_stderr "📜 Modulefile path: $script_path"
    # if target directory exists, exit 1
    if [ -d "$target_dir" ]; then
        print_stderr "${RED}ERROR${NC}: Target app exists!"
        print_stderr "Exit Installing"
        exit 1
    fi

    print_stderr "Checking dependencies for ${YELLOW}${app_name_version}${NC}"
    install_dependencies
    load_dependencies

    install_app
    copy_modulefile
    print_stderr "✅ Installation completed. ${YELLOW}${app_name_version}${NC} is ready to use."
}

remove_target_directory() {
    print_stderr "Removing target directory: $target_dir"
    if [[ -d "$target_dir" ]]; then
        rm -rf "$target_dir"
        del_dir="$(dirname "$target_dir")"
        while [[ "$del_dir" != "$modules_root" ]]; do
            if [[ -z "$(ls -A "$del_dir")" ]]; then
                print_stderr "Parent directory is empty. Removing $del_dir"
                rmdir "$del_dir"
                del_dir="$(dirname "$del_dir")"
            else
                break
            fi
        done
    fi

    # restore terminal settings in case interrupted during a `read` or similar
    stty sane 2>/dev/null || true
}

remove_modulefile() {
    print_stderr "Removing modulefile: $script_path"
    if [[ -f "$script_path" ]]; then
        rm -rf "$script_path"
        rm -rf "${script_path}.lua"
        del_dir="$(dirname "$script_path")"
        while [[ "$del_dir" != "$modules_root" ]]; do
            if [[ -z "$(ls -A "$del_dir")" ]]; then
                print_stderr "Parent directory is empty. Removing $del_dir"
                rmdir "$del_dir"
                del_dir="$(dirname "$del_dir")"
            else
                break
            fi
        done
    fi
}

delete() {
    print_stderr "Deleting the target module: ${YELLOW}${app_name_version}${NC}"
    # if target directory does not exist, exit 1
    if [ ! -d "$target_dir" ]; then
        print_stderr "${RED}ERROR${NC}: Target app does not exist!"
        print_stderr "Exit Removing"
        exit 1
    fi

    remove_target_directory
    remove_modulefile
    print_stderr "Deletion completed. ${YELLOW}${app_name_version}${NC} is removed."
    exit
}

is_installed() {
    if [ -d "${modules_root}/${target}/${1}" ]; then
        echo 0
    else
        echo 1
    fi
}

print_dependencies() {
    printf "${YELLOW}$app_name_version${NC} dependencies:\n" 1>&2
    # Print the dependencies
    if [ -n "$dependencies" ]; then
        for dep in $dependencies; do
            printf "  ${BLUE}${dep}${NC}" 1>&2
            if [ $(is_installed "${dep}") -eq 0 ]; then
                printf " (installed)\n" 1>&2
            else
                printf "\n" 1>&2
            fi
        done
    fi
}

install_dependencies() {
    # Install the dependencies
    for dep in $dependencies; do
        if [ $(is_installed "${dep}") -eq 0 ]; then
            continue
        fi
        print_stderr "Installing dependency: ${BLUE}${dep}${NC} for ${YELLOW}${app_name_version}${NC}"
        "$manager_script" -i "$dep"
    done
}

load_dependencies() {
    # Load the dependencies in the current shell
    autoload=$(grep -oP "^#AUTOLOAD_DEPENDENCY:\K.*" "$install_script_path" | cut -d' ' -f1)
    if [ -n "$autoload" ]; then
        if [[ "$autoload" =~ ^(FALSE|False|false)$ ]]; then
            return 0
        fi
    fi

    for dep in $dependencies; do
        print_stderr "Loading dependency: ${BLUE}${dep}${NC}"
        module load $dep &> /dev/null # suppress output
    done
}

copy_modulefile() {
    print_stderr "Copying modulefile to $script_path"
    mkdir -p "$script_base_dir"
    if [ -f "${modules_root}/build-scripts/${app_name}/template" ]; then
        print_stderr "${YELLOW}${app_name}${NC} specific template exists. Use it."
        cat "${modules_root}/build-scripts/${app_name}/template" > "$script_path"
        cat "${modules_root}/build-scripts/${app_name}/template.lua" > "${script_path}.lua"
    else
        print_stderr "${YELLOW}${app_name}${NC} specific template does not exist. Use default template."
        cat "${modules_root}/build-scripts/${target}-template" > "$script_path"
        cat "${modules_root}/build-scripts/${target}-template.lua" > "${script_path}.lua"
    fi

    print_stderr "Editing the modulefile to include the dependencies"
    for dep in $dependencies; do
        dep_name="${dep%/*}"
        dep_version="${dep#*/}"
        print_stderr "Adding dependency: ${BLUE}${dep_name}/${dep_version}${NC}"
        echo "# Dependency: ${dep_name}/${dep_version}" >> "${script_path}"
        echo "module load ${dep_name}/${dep_version}" >> "${script_path}"
        echo "-- Dependency: ${dep_name}/${dep_version}" >> "${script_path}.lua"
        echo "depends_on(\"${dep_name}/${dep_version}\")" >> "${script_path}.lua"
    done

    # edit whatis if #WHATIS: is found in the script
    whatis=$(grep -oP "^#WHATIS:\K.*" "$install_script_path" || true)
    whatis=${whatis:-"Loads ${app_name_version}"}
    print_stderr "Editing ${BLUE}whatis${NC} in modulefile"
    # Replace the place holder ${WHATIS} in the modulefile
    sed -i "s|\${WHATIS}|${whatis}|" "${script_path}"
    sed -i "s|\${WHATIS}|${whatis}|" "${script_path}.lua"

    url=$(grep -oP "^#URL:\K.*" "$install_script_path" || true)
    url=${url:-"No additional information available."}
    print_stderr "Editing ${BLUE}help${NC} in modulefile"
    # Replace the place holder ${URL} in the modulefile
    sed -i "s|\${HELP}|WEBSITE: ${url}|" "${script_path}"
    sed -i "s|\${HELP}|WEBSITE: ${url}|" "${script_path}.lua"
    special_modulefiles
}
#endregion

#region UTILITIES
print_stderr() {
    printf "[`date +"%Y-%m-%d %T"`] $1\n" 1>&2
}

pigz_or_gunzip() {
    if command -v pigz &> /dev/null; then
        pigz -d -p $ncpu "$1"
    else
        gunzip "$1"
    fi
}

remove_default_dependencies() {
    dep_name="$1"

    awk -v dep="$dep_name" '
        # Remove tcl dependencies
        $0 ~ "^# Dependency: " dep   { next }
        $0 ~ "module load " dep      { next }
        { print }
    ' "$script_path" > "$script_path.tmp" &&
    mv "$script_path.tmp" "$script_path"

    awk -v dep="$dep_name" '
        # Remove Lua dependencies
        $0 ~ "^-- Dependency: " dep  { next }
        $0 ~ "depends_on\\(\"" dep   { next }
        { print }
    ' "${script_path}.lua" > "${script_path}.lua.tmp" &&
    mv "${script_path}.lua.tmp" "${script_path}.lua"
}


# Function to clean up the temporary directory
clean_up () {
    [[ $cleanup_called -eq 1 ]] && return 0
    cleanup_called=1

    status="$1"   # 0 = success, 1 = error
    sleep 1
    cd "$modules_root"

    if [[ "$status" == "1" ]]; then
        print_stderr "Removing incomplete installation."
        print_error_message
        remove_target_directory
        remove_modulefile
    elif [[ -d "$tmp_dir" ]]; then
        print_stderr "Removing temporary directory: $tmp_dir"
        rm -rf "$tmp_dir"
        del_dir="$(dirname "$tmp_dir")"
        while [[ "$del_dir" != "$modules_root" ]]; do
            if [[ -z "$(ls -A "$del_dir")" ]]; then
                print_stderr "Parent directory is empty. Removing $del_dir"
                rmdir "$del_dir"
                del_dir="$(dirname "$del_dir")"
            else
                break
            fi
        done
    fi
}

print_error_message() {
    # Custom error message can be defined in the build script
    print_stderr "Possible Reason: Missing dependencies or Expired links"
}
#endregion

#region MAIN
main() {
    if [ "$#" -eq 0 ]; then
        print_stderr "${RED}ERROR${NC}: No option provided."
        help_message
        exit 1
    fi

    # Parse the parameters
    while getopts ":hdil" opt; do
        case ${opt} in
            h ) help_message ; exit;;
            i ) install ;;
            l ) print_dependencies ;;
            d ) delete ;;
            \? )
                print_stderr "${RED}ERROR${NC}: Invalid option: $OPTARG"
                help_message
                exit 1
                ;;
        esac
    done
}
#endregion
