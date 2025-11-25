# Environment Module for Bioinfo Research

> [!IMPORTANT] When to use this repo?
> Personally, I recommend you to use `conda`, `mamba`, `micromamba`, or `pixi` for manage project environments. 
> 
> This repo aims to provide quick and reproducible environment modules for lab-wide use, especially for labs that need to switch between different workstations, servers, and clusters.

## Overview

There are two types of modules in this repo:

- [apps](#apps-modules): bioinformatics software applications
- [ref](#ref-modules): reference data and their indexes
  
If a package in available in conda-forge/bioconda, you can use `./manager.py -i <app>/<version>` to install it automatically.

If you want to install a package that is not available in conda-forge/bioconda, you can create your own installation script under `build-scripts/<app>/<version>`. e.g. [cellranger/9.0.1](build-scripts/cellranger/9.0.1). then

- `./manager.py -i cellranger/9.0.1` to install it. or
- `./build-scripts/cellranger/9.0.1 -i` to install it.

You can search for available packages on [anaconda.org](https://anaconda.org).

## Prerequisites

Before using the modules, make surue:

1. Have either Environment Modules or Lmod installed.
2. Make sure `module` uses the following two paths, by adding them to your `$HOME/.bashrc`:

```bash
# Please run the following command in the module folder
cat << EOF >> $HOME/.bashrc
# Add custom modulefiles path
if type module >/dev/null 2>&1 && [ -d "$(readlink -f $PWD)" ]; then
    module use $(readlink -f $PWD)/apps_modulefiles
    module use $(readlink -f $PWD)/ref_modulefiles
fi
EOF
```

## Apps Modules

- Build scripts: `build-scripts/<app>/<version>`
- Target installation path: `apps/<app>/<version>/`
- Modulefiles path: `apps_modulefiles/<app>/<version>`

When you install an app module:

- If the app is available in conda-forge/bioconda, use `./manager.py -i <app>/<version>` to install.
- For the apps not available in conda-forge/bioconda, you need to create your own installation script `build-scripts/<app>/<version>`, e.g. [cellranger/9.0.1](build-scripts/cellranger/9.0.1).

Example apps module names:

- `fastqc/0.12.1`
- [cellranger/9.0.1](build-scripts/cellranger/9.0.1)

## Ref Modules

- Build scripts: `build-scripts/<assembly>/<data-type>/<version>`
- Target installation path: `ref/<assembly>/<data-type>/<version>/`
- Modulefiles path: `ref_modulefiles/<assembly>/<data-type>/<version>`

Example ref module names:

- [grch38/genome/gencode](build-scripts/grch38/genome/gencode)
- [grcm39/transcript/gencodeM33](build-scripts/grcm39/transcript/gencodeM33)
- [grch38/gtf/gencode44](build-scripts/grch38/gtf/gencode44)
- [grch38/star-2.7.11b/gencode44-151](build-scripts/grch38/star-2.7.11b/gencode44-151)
- [grch38/salmon-1.10.3/gencode44](build-scripts/grch38/salmon-1.10.3/gencode44)

## Manager Script: [manager.py](manager.py)

The manager script utilizes the conda-forge and bioconda databases to download all pre-compiled binaries and create modulefiles for them.

Usage: `./manager.py [options] <app>/<version>`

Quick example:

```bash
# Try to get package info for sra-tools from conda-forge/bioconda
./manager.py -a sra-tools
# Install the latest version of sra-tools
./manager.py -i sra-tools
# Install sra-tools with latest version matching 3.*
./manager.py -i sra-tools/3*

# Remove sra-tools version 3.1.1
./manager.py -d sra-tools/3.1.1
# Search for packages related to "aligner"
./manager.py -s aligner
# Show detailed info for package "fastqc"
./manager.py -I fastqc
# Update the local packages
./manager.py -u
# Update both local and remote packages
./manager.py -U
```

## Custom Packages `build-scripts/<app>/<version>`

Usage: `./build-scripts/<app>/<version> [options]`

options:

- `-i`  Install the target module with its dependencies.
- `-d`  Delete the target module.
- `-h`  Help message.

e.g.

```bash
# Install
./build-scripts/vg/1.61.0 -i
./build-scripts/grch38/salmon-1.10.3/gencode44 -i

# Remove
./build-scripts/vg/1.61.0 -d
./build-scripts/grch38/salmon-1.10.3/gencode44 -d
```

## Multi-threading Support

If you want to increase the number of threads, you can set env `SLURM_CPUS_PER_TASK`. If you are using slurm, it will automatically use the number of cpus allocated.

```bash
SLURM_CPUS_PER_TASK=16 ./build-scripts/<app>/<version> -i

# e.g. Build salmon index with 16 threads
SLURM_CPUS_PER_TASK=16 ./build-scripts/data-index/salmon-grch38-gencode47 -i
# or
SLURM_CPUS_PER_TASK=16 ./manager.py -i data-index/salmon-grch38-gencode47
```

## How to create your own module

Please go to [build-scripts/README.md](build-scripts/README.md) for detailed instructions.
