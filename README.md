# Environment Module for Bioinfo Research

Make sure you run `module use /somewhere/modules` to use these modules.

---

There are two similar environment-control softwares: [Environment Modules](https://modules.sourceforge.net/) and [Lmod](https://lmod.readthedocs.io/en/latest/index.html)

- Lmod uses the Lua, while Environment Modules uses Tcl module scripts (similar to shell script)
- They have the same usage:
  - `module use /somewhere/modulefiles` use custom modulefiles
    - modulefile's content starts with `#%Module1.0`
    - Lmod filename ends with `.lua`
  - `module avail [name]` check all modules, name is optional
  - `module load cellranger/8.0.1`
  - `module unload cellranger/8.0.1`
  - `module purge` unload all modules

## How to Build Custom Modules

### Install

1. go into `modules` folder
2. run build scripts, e.g. `bash build-scripts/sra-tools/3.1.1`
   - Do not run `sbatch build-scripts/sra-tools/3.1.1`, otherwise the script cannot catch the script name
      - like `/opt/slurm/data/slurmd/job53753702/slurm_script`
   - Use a script to wrap it or use `srun --time=6:00:00 bash build-scripts/sra-tools/3.1.1`

Most of my scripts are **version independent**. It will automatically download the same version as the file name.  If a new version is available, simply copy the old one to a file named that version.

For example, `sra-tools` version `3.2.1` comes out. `cp build-scripts/sra-tools/3.1.1 build-scripts/sra-tools/3.2.1`. Then run that script.

### Remove

1. go into `modules` folder
2. run build scripts with `-d` parameter, e.g. `bash build-scripts/sra-tools/3.1.1 -d`
   - `-d` for deleting

## Version Dependent Packages

goto [build-scripts README](build-scripts/README.md) for detailed

- [Cell Ranger](build-scripts/README.md#cell-ranger)
  - You need key-pair to download the it. If it fails, change the link.
  - https://www.10xgenomics.com/support/software/cell-ranger/downloads/previous-versions

## Setup Environment Modules

It is installed by default on Redhat. In Ubuntu, you need to install and init it.

```bash
sudo apt update -y
sudo apt install -y environment-modules

# add to global settings
sudo sh -c 'echo "
# Enable Environment Modules
if [ -f /etc/profile.d/modules.sh ]; then
    . /etc/profile.d/modules.sh
fi
" >> /etc/bash.bashrc'
```

If you have custom modulefiles, You can add `module use`.

## How it works?

You can config the environment variables in modulefile.

```tcl
# add app bin at the beginning of the PATH
prepend-path PATH $app_root/bin

# set custom environment variable
setenv CELLRANGER_REF $ref_root
```

When you run `module load/unload`, modules can help use set or unset `PATH` and other variables.

### Directory Structure

- root directory is `modules`
- apps and versions are under `modules`
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
├── cellranger/
│   ├── 7.0.1/
│   │   ├── bin/
│   │   └── lib/
│   ├── 8.0.1/
│   │   ├── bin/
│   │   └── lib/
│   └── ref/
│       ├── refdata-gex-GRCh38-2020-A/
│       └── refdata-gex-GRCh38-2024-A/
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

- [modulefile template](build-scripts/template)
- [Lmod template.lua](build-scripts/template.lua)

Where to store:

- It should be stored in `somewhere/modulefiles/app/x.y.z` (file)
- Target app is in `somewhere/app/x.y.z/` (directory)


