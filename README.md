# Environment Module

There are two similar environment-control softwares: [Environment Modules](https://modules.sourceforge.net/) and [Lmod](https://lmod.readthedocs.io/en/latest/index.html)

- Lmod uses the Lua, while Environment Modules uses Tcl module scripts (similar to shell script)
  - You can use ChatGPT to convert them interchangeably.
- They have the same usage:
  - `module use /somewhere/modulefiles` use custom modulefiles
    - modulefiles starts with `#%Module1.0`
    - Lmod file name ends with `.lua`
  - `module avail [name]` check all modules, name is optional
  - `module load cellranger/8.0.1`
  - `module unload cellranger/8.0.1`
  - `module purge` unload all modules

## Setup

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

## Directory Structure

- root directory is `module`
- apps and versions are under `module`
- corresponding modulefiles are under `module/modulefiles`

Example Directory Structure

```
modules/
├── modulefiles/
│   ├── cellranger/
│   │   ├── 7.0.1
│   │   └── 8.0.1
│   ├── sra-tools
│   │   └── 3.1.1
│   └── template
│       └── 1.0.0
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

## Relative Path in Modulefile

```tcl
# get absolute path of this module file, like /share/apps/modulefiles/
set abs_path [file normalize [info script]]

# get the path to modulefiles
set app_full_name [module-info name]
```

## Template script

- [modulefile template](modulefiles/template/1.0.0)
- [Lmod template.lua](modulefiles/template/1.0.0.lua)

Where to store:

- It should be stored in `somewhere/modulefiles/app/x.y.z` (file)
- Target app is in `somewhere/app/x.y.z/` (directory)


