#!/bin/bash

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
app_name_version="${install_script_path#*/build-scripts/}" # name/version
app_name="${app_name_version%/*}"  # name
version="${app_name_version##*/}"  # version

target_base_dir="${modules_root}/apps/${app_name}"      # modules/apps/name
target_dir="${modules_root}/apps/${app_name_version}"   # modules/apps/name/version
script_base_dir="${modules_root}/modulefiles/${app_name}"      # modules/modulefiles/name
script_path="${modules_root}/modulefiles/${app_name_version}"  # modules/modulefiles/name/version

tmp_dir="${modules_root}/tmp/${app_name_version}" # tmp directory
#endregion

#region OPTION_FUNCTIONS
help_message() {
    echo "Usage: bash $0 [options]" 1>&2
    echo "Options:" 1>&2
    echo "  -i  Install the target module with dependencies." 1>&2
    echo "  -o  Only install the target module without dependencies." 1>&2
    echo "  -l  List the dependencies of the target module." 1>&2
    echo "  -d  Delete the target module." 1>&2
    echo "  -s  Set this version as the default version." 1>&2
    echo "  -h  Help message." 1>&2
}

install() {
    # $1 == only to skip the dependencies
    print_stderr "Installing the target module: ${YELLOW}${app_name_version}${NC}"
    print_stderr "Target directory: $target_dir"
    print_stderr "Modulefile path: $script_path"
    # if target directory exists, exit 1
    if [ -d "$target_dir" ]; then
        print_stderr "${RED}ERROR${NC}: Target app exists!"
        print_stderr "Exit Installing"
        exit 1
    fi
    if [ "$1" != only ]; then # skip the dependencies if $1 == only
        print_stderr "Checking dependencies."
        dependencies=$(get_dependencies)
        check_dependencies "$dependencies"
        install_dependencies "$dependencies"
    fi
    install_app
    copy_modulefile
    clean_up 0
    print_stderr "Installation completed. ${YELLOW}${app_name_version}${NC} is ready to use."
}

delete() {
    print_stderr "Deleting the target module: ${YELLOW}${app_name_version}${NC}"
    print_stderr "Target directory: $target_dir"
    print_stderr "Modulefile path: $script_path"
    # if target directory does not exist, exit 1
    if [ ! -d "$target_dir" ]; then
        print_stderr "${RED}ERROR${NC}: Target app does not exist!"
        print_stderr "Exit Removing"
        exit 1
    fi

    # modules/apps/name/version
    rm -rf "$target_dir"
    # modulefiles/name/version
    rm -rf "$script_path"
    rm -rf "${script_path}.lua"

    # If the modules/apps/name directory is empty, remove it
    if [ -z "$(ls -A $target_base_dir)" ]; then
        print_stderr "App directory is empty. Removing $target_base_dir"
        rm -rf "$target_base_dir"
    fi
    # If the modulefiles/name directory is empty, remove it
    if [ -z "$(ls -A $script_base_dir)" ]; then
        print_stderr "Modulefiles directory is empty. Removing $script_base_dir"
        rm -rf "$script_base_dir"
    fi
    print_stderr "Deletion completed. ${YELLOW}${app_name_version}${NC} is removed."
    exit
}

set_default() {
    print_stderr "Setting this version as the default version: $target_dir"
    # if target directory does not exist, exit 1
    if [ ! -d "$target_dir" ]; then
        print_stderr "${RED}ERROR${NC}: Target app does not exist!"
        print_stderr "Exit Setting Default"
        exit 1
    fi

    # Create .version file under modulefiles/name
    echo "#%Module" > "${script_base_dir}/.version"
    echo "set ModulesVersion $version" >> "${script_base_dir}/.version"
    exit
}

get_dependencies() {
    # Get the dependencies from the script and put them to stdout
    for dep in $(grep -oP "^#DEPENDENCY:\K.*" "$install_script_path"); do
        if [[ "$dep" =~ \* ]]; then
            dep_name="${dep%/*}"
            version_pattern="${dep#*/}"
            versions="$(ls ${modules_root}/build-scripts/${dep_name}/$version_pattern | xargs -n 1 basename | grep -v "^template")"
            if [ $? -ne 0 ] || [ -z "$versions" ]; then
                print_stderr "${RED}ERROR${NC}: Dependency not found: ${BLUE}${dep_name}${NC}"
                exit 1
            fi
            echo "${dep_name}/$(echo "$versions" | sort -V | tail -n 1)"
        else
            echo "$dep"
        fi
    done
}

is_installed() {
    # $1: app_name $2: version
    if [ -d "${modules_root}/apps/${1}/${2}" ]; then
        echo 0
    else
        echo 1
    fi
}

check_dependencies() {
    # Exit 1 if any dependency is not found
    for dep in $1; do
        dep_name="${dep%/*}"
        dep_version="${dep#*/}"
        if [ ! -x "${modules_root}/build-scripts/${dep_name}/${dep_version}" ]; then
            print_stderr "${RED}ERROR${NC}: Dependency not found: ${BLUE}${dep_name}/${dep_version}${NC}"
            exit 1
        fi
    done
}

print_dependencies() {
    printf "${YELLOW}$app_name_version${NC} dependencies:\n" 1>&2
    dependencies=$(get_dependencies)
    # Print the dependencies
    if [ -n "$dependencies" ]; then
        for dep in $dependencies; do
            printf "  ${BLUE}${dep%/*}${NC}/${dep#*/}" 1>&2
            if [ $(is_installed "${dep%/*}" "${dep#*/}") -eq 0 ]; then
                printf " (installed)\n" 1>&2
            else
                printf "\n" 1>&2
            fi
        done
    fi
}

install_dependencies() {
    # Install the dependencies
    for dep in $1; do
        dep_name="${dep%/*}"
        dep_version="${dep#*/}"
        if [ $(is_installed "$dep_name" "$dep_version") -eq 0 ]; then
            print_stderr "${BLUE}${dep_name}/${dep_version}${NC} is already installed."
        else
            print_stderr "Installing dependency: ${BLUE}${dep_name}/${dep_version}${NC}"
            run_command cd "${modules_root}" && bash "build-scripts/${dep_name}/${dep_version}" -i
            if [ $? -ne 0 ]; then
                print_stderr "${RED}ERROR${NC}: Dependency installation failed: ${BLUE}${dep_name}/${dep_version}${NC}"
                exit 1
            fi
        fi
    done
}

copy_modulefile() {
    print_stderr "Copying modulefile to $script_path"
    mkdir -p "$script_base_dir"
    if [ -f "${modules_root}/build-scripts/${app_name}/template" ]; then
        print_stderr "${YELLOW}${app_name}${NC} specific template exists. Use it."
        cp "${modules_root}/build-scripts/${app_name}/template" "$script_path"
        cp "${modules_root}/build-scripts/${app_name}/template.lua" "${script_path}.lua"
    else
        print_stderr "${YELLOW}${app_name}${NC} specific template does not exist. Use default template."
        cp "${modules_root}/build-scripts/template" "$script_path"
        cp "${modules_root}/build-scripts/template.lua" "${script_path}.lua"
    fi

    print_stderr "Editing the modulefile to include the dependencies"
    for dep in $(get_dependencies); do
        dep_name="${dep%/*}"
        dep_version="${dep#*/}"
        print_stderr "Adding dependency: ${BLUE}${dep_name}/${dep_version}${NC}"
        echo "# Dependency: ${dep_name}/${dep_version}" >> "${script_path}"
        echo "module load ${dep_name}/${dep_version}" >> "${script_path}"
        echo "-- Dependency: ${dep_name}/${dep_version}" >> "${script_path}.lua"
        echo "depends_on(\"${dep_name}/${dep_version}\")" >> "${script_path}.lua"
    done

    # edit whatis if #WHATIS: is found in the script
    whatis=$(grep -oP "^#WHATIS:\K.*" "$install_script_path")
    if [ -n "$whatis" ]; then
        print_stderr "Editing ${BLUE}whatis${NC} in modulefile"
        sed -i "s|^module-whatis.*|module-whatis \"${whatis}\"|" "${script_path}"
        sed -i "s|^whatis.*|whatis(\"${whatis}\")|" "${script_path}.lua"
    fi

    special_modulefiles
}
#endregion

#region UTILITIES
print_stderr() {
    printf "[`date +"%Y-%m-%d %T"`] $1\n" 1>&2
}

# Function to clean up the temporary directory
clean_up () {
    cd "$modules_root"
    sleep 1 # wait for the release of the file handle
    # if $1 is 1, building failed. Do not remove the temporary directory
    if [ "$1" == 1 ]; then
        print_stderr "Removing target directory: $target_dir"
        rm -rf "$target_dir"
    # successful building. Remove the temporary directory if it exists
    elif [ -d "$tmp_dir" ]; then
        print_stderr "Removing temporary directory: $tmp_dir"
        # keep deleting empty directories until the $module_root dir
        rm -rf "$tmp_dir"
        del_dir="$(dirname $tmp_dir)"
        while [ "$del_dir" != "$modules_root" ]; do
            if [ -z "$(ls -A $del_dir)" ]; then
                print_stderr "Parent directory is empty. Removing $del_dir"
                rmdir "$del_dir"
                del_dir="$(dirname "$del_dir")"
            else
                break
            fi
        done
    fi
}

# run the command in a sub shell to avoid issues when cleaning up
# cp mv wget or other file operations (it seems rm issue is fixed by adding sleep 1)
sub_shell() {
    msg=$($@)
    result=$?
    if [ -n "$msg" ]; then
        print_stderr "$msg"
    fi
    return $result
}

# Function to run a command and exit if it fails
run_command() {
    sub_shell $@
    if [ $? -ne 0 ]; then
        print_stderr "${RED}ERROR${NC}: Command failed: $@"
        print_stderr "Possible Reason: Missing dependencies or Expired links"
        print_stderr "PWD: `pwd`"
        clean_up 1
        exit 1
    fi
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
    while getopts ":hdiols" opt; do
        case ${opt} in
            h ) help_message ; exit;;
            i ) install ;;
            o ) install only ;;
            l ) print_dependencies ;;
            s ) set_default ;;
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
