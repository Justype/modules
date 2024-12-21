# Environment Module for Bioinfo Research

Make sure you run `module use /somewhere/modules/modulefiles` to use these modules.

---

Usage: `bash build-scripts/app_name/version [options]`

options:

- `-i`  Install the target module.
- `-d`  Delete the target module.
- `-s`  Set this version as the default version. (Not working if `tclsh` is missing)
- `-h`  Help message.

## How to Build Custom Modules

### Install

1. go into `modules` folder
2. run build scripts with `-i`, e.g. `bash build-scripts/sra-tools/3.1.1 -i`

Most of my scripts are **version independent**. It will automatically download the same version as the file name.  If a new version is available, simply create a symlink to the old one.

For example, `sra-tools` version `3.2.1` comes out. `ln -s build-scripts/sra-tools/3.1.1 build-scripts/sra-tools/3.2.1`. Then run that script.

#### Do use `sbatch` to install

- My script use its name and path to find version and installation path.
- The `sbatch` will save this script to its own directory:
  - like `/opt/slurm/data/slurmd/job53753702/slurm_script`
- Use a script to wrap it or use `srun`

### Remove

1. go into `modules` folder
2. run build scripts with `-d`, e.g. `bash build-scripts/sra-tools/3.1.1 -d`

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
```

If you have custom modulefiles, You can add `module use` to your `$HOME/.bashrc`.

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

- It should be stored in `somewhere/modulefiles/name/x.y.z` (file)
- Target app is in `somewhere/apps/name/x.y.z/` (directory)
