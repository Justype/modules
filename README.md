# Environment Module for Bioinfo Research

Make sure you run `module use /somewhere/modules/modulefiles` to use these modules.

Personally, I recommend you to use `conda` or `mamba` for most of the bioinfo tools. But if you want to use environment modules/lmod, this is a good place to start.

If a package in available in bioconda/conda-forge, you can use `./manager.py -i <app>/<version>` to install it automatically.

If you want to install a package that is not available in bioconda/conda-forge, you can create your own installation script under `build-scripts/<app>/<version>`. e.g. [cellranger/9.0.1](build-scripts/cellranger/9.0.1).

You can search for available packages on [anaconda.org](https://anaconda.org).

## TOC

- [How to Install/Remove Custom Modules](#how-to-installremove-custom-modules)
- [Setup Environment Modules](#setup-environment-modules)
- [How to create your own module](#how-to-create-your-own-module)
- [How does modules work?](#how-does-module-work)
- [Template script](#template-script)

## Manager Script: [manager.py](manager.py)

The manager script utilizes the conda-forge and bioconda databases to download all pre-compiled binaries and create modulefiles for them.

Usage: `./manager.py [options] <app>/<version>`

Quick example:

```bash
# Try to get package info for sra-tools and add it to the local database
./manager.py -a sra-tools
# Install the latest version of sra-tools
./manager.py -i sra-tools
# Install sra-tools with version 3.*
./manager.py -i sra-tools/3*

# Remove sra-tools version 3.1.1
./manager.py -d sra-tools/3.1.1
# Search for packages related to "aligner"
./manager.py -s aligner
# Show detailed info for package "fastqc"
./manager.py -I fastqc
# Update the local database
./manager.py -u
```

## Custom Packages `build-scripts/<app>/<version>`

Usage: `./build-scripts/<app>/<version> [options]`

options:

- `-i`  Install the target module with its dependencies.
- `-d`  Delete the target module.
- `-h`  Help message.

If you want to increase the number of threads, you can set env `SLURM_CPUS_PER_TASK`. If you are using slurm, it will automatically use the number of cpus allocated.

```bash
SLURM_CPUS_PER_TASK=16 ./build-scripts/<app>/<version> -i

# e.g. Build salmon index with 16 threads
SLURM_CPUS_PER_TASK=16 ./build-scripts/data-index/salmon-grch38-gencode47 -i
# or
SLURM_CPUS_PER_TASK=16 ./manager.py -i data-index/salmon-grch38-gencode47
```

## How to Install/Remove Custom Modules

### Install

1. go into `modules` folder
2. `./manager.py -i <app>/<version>`

### Remove

Currently can only remove one version at a time. Cannot remove the dependency automatically.

1. go into `modules` folder
2. `./manager.py -d <app>/<version>`

## Setup Environment Modules

You can either use Environment Modules or Lmod.

```bash
# install Environment Modules
sudo apt update -y
sudo apt install -y environment-modules
```

```bash
# install Lmod
sudo apt update -y
sudo apt install -y lmod
```

If you have custom modulefiles, You can add `module use <path>/modules/modulefiles` to your `$HOME/.bashrc`.

## How to create your own module

Example: [sra-tools/3.1.1](build-scripts/sra-tools/3.1.1)

What does the script do?

1. Download the app source code or binary.
2. If your app has dependencies, it will automatically install them first.
3. Extract the source code or binary to `tmp/app_name/app_version/`.
4. If it is a source code, compile it.
5. Copy the binary files to `modules/apps/app_name/app_version/`. (make sure executable is in `bin/`)
6. Copy the modulefile to `modules/modulefiles/app_name/app_version/`.
    - By default, it will use the `build-scripts/template` or `build-scripts/template.lua` as the template.
    - If you have your own modulefile, you can put them in `build-scripts/<app_name>/template(.lua)` and it will be used instead.
7. Edit the modulefile `whatis` and `description` fields.
8. After the installation, `tmp` directory will be removed unless failed.

### Available Installation Templates

- [normal_template](build-scripts/0-template/normal_template)
- [python27_template](build-scripts/0-template/py27_template)
- [python311_template](build-scripts/0-template/py311_template)

### What you need to do to make your own installation script

1. Copy one of the templates to `build-scripts/<app_name>/<version>`.
2. Edit the script to download the source code or binary.
3. Set the right dependencies at the top of the script.
4. Set a correct `whatis` at the top of the script.
5. If you need to set custom environment variables, you can either:
    - Edit the modulefile in `special_modulefiles()` function..
    - Or create a custom modulefile named `build-scripts/<app_name>/template(.lua)` and it will be used instead of the default template.

### How to set dependencies

You need to set `#DEPENDENCY:<name>/<version>` at the top of your installation script.

This is an example of [picard/3.3.0](backup/build-scripts/picard/3.3.0). Here I set `picard` depends on `java` 21.

```bash
#!/usr/bin/bash
#DEPENDENCY:jdk/21*
#WHATIS:Manipulating seq data and formats
```

If you do in this way, it will automatically install `jdk/21.0.5` if it is not installed.

### How to set `whatis`

You can set `#WHATIS:` at the top of your installation script.

This is an example of [sra-tools/3.1.1](build-scripts/sra-tools/3.1.1).

```bash
#!/usr/bin/bash
#WHATIS:Download data from the Sequence Read Archive (SRA)
```

If you run `module whatis sra-tools`, it will show the description you set here.

```
$ module whatis sra-tools
----------------- /opt/software/modules/modulefiles -----------------
sra-tools/3.1.1: Download data from the Sequence Read Archive (SRA)
```

### How to set custom environment variables

Either:

- Edit the modulefile in `special_modulefiles()` function.
- Or create a custom modulefile named `build-scripts/<app_name>/template(.lua)` and it will be used instead of the default template.

#### Example of special_modulefiles()

In [bcftools/1.21](build-scripts/bcftools/1.21), I set the `BCFTOOLS_PLUGINS` environment variable.

```bash
special_modulefiles() {
    print_stderr "Adding ${BLUE}BCFTOOLS_PLUGINS${NC} environment variable"
    echo "setenv BCFTOOLS_PLUGINS \"\$app_root/libexec/bcftools\"" >> "$script_path"
    echo "setenv(\"BCFTOOLS_PLUGINS\", pathJoin(app_root, \"libexec\", \"bcftools\"))" >> "${script_path}.lua"
}
```

These will edit `modules/modulefiles/bcftools/1.21` and `modules/modulefiles/bcftools/1.21.lua` to add the environment variable.

#### Example of custom modulefile

In [micromamba](build-scripts/micromamba/), I created a custom modulefile `build-scripts/micromamba/template(.lua)` to have better prompt.

In [orad](build-scripts/orad/), I added custom environment variables in [orad/2.7.0](build-scripts/orad/2.7.0).

How to set your own custom modulefile? see the next section.

## How does module work?

You can config the environment variables in modulefile, using `setenv`, `prepend-path`, `append-path`, etc.

- When you run `module load <app>/<version>`, it will set the environment variables defined in the modulefile.
- When you run `module unload <app>/<version>`, it will unset the environment variables defined in the modulefile.

### Environment Modules

It uses Tcl script to set environment variables.

```tcl
# add app bin at the beginning of the PATH
prepend-path PATH $app_root/bin

# set custom environment variable
setenv BCFTOOLS_PLUGINS "$app_root/libexec/bcftools"
```

### Lmod

Lmod uses Lua script to set environment variables.

```lua
-- add app bin at the beginning of the PATH
prepend_path("PATH", pathJoin(app_root, "bin"))

-- set custom environment variable
setenv("BCFTOOLS_PLUGINS", pathJoin(app_root, "libexec", "bcftools"))
```

When you run `module load/unload`, modules can help use set or unset `PATH` and other variables.

### Directory Structure

- root directory is `modules`
- apps and versions are under `modules/apps`
- corresponding modulefiles are under `modules/modulefiles`

Example Directory Structure

```
modules/
├── modulefiles/
│   ├── cellranger/
│   │   ├── 7.0.1
│   │   └── 8.0.1
│   └── sra-tools
│       └── 3.1.1
└── apps/
    ├── cellranger/
    │   ├── 7.0.1/
    │   │   ├── bin/
    │   │   └── lib/
    │   └── 8.0.1/
    │       ├── bin/
    │       └── lib/
    └── sra-tools/
        └── 3.1.1/
            └──  bin/
```

### Relative Path in Modulefile

```tcl
# get absolute path of this module file, like /share/apps/modulefiles/
set abs_path [file normalize [info script]]

# get the path to modulefiles
set app_full_name [module-info name]

# get parent directory from a path
set app_modulefiles_dir [file dirname $abs_path]

# get file or dir name from a path
set name [file tail $abs_path]
```

## Template script

- [modulefile template](build-scripts/template) (Tcl script for Environment Modules)
- [Lmod template.lua](build-scripts/template.lua) (Lua script for Lmod)

Where to store:

- Module file should be stored as `somewhere/modulefiles/name/x.y.z` (file)
- Its target app is under `somewhere/apps/name/x.y.z/` (directory)
