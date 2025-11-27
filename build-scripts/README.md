# Custom Build Scripts and Environment Modules

The `build-scripts/` folder contains custom scripts to build bioinformatics tools and genome references, along with environment modulefiles to load them easily.

There are two types of build scripts: (depends on the number of slashes in the path)

- apps: scripts to build bioinformatics tools (e.g. `cellranger/9.0.1`)
- refs: scripts to build genome references (e.g. `grch38/genome/gencode`)

Template modules files are under `build-scripts/`

- `apps-template(.lua)`: template for building app modulefiles (also used for conda packages)
- `refs-template(.lua)`: template for building reference modulefiles

To differentiate them, the variable names are different: [apps](#apps-templatelua) vs [refs](#refs-templatelua)

`apps` template modules works perfectly fine. `ref` template is still OK to use. But to add more help information, it is recommended to modify the template file in build script.

## TOC

- [Environment Modules and Lmod](#environment-modules-and-lmod)
- [Template Modulefiles](#template-modulefiles)
- [apps modules](#apps-modules)
- [apps build script example](#apps-build-script-example)
- [ref modules](#ref-modules)
- [ref build script example](#ref-build-script-example)
- [common.sh](#commonsh)

## Environment Modules and Lmod

There are two similar environment-control softwares: [Environment Modules](https://modules.sourceforge.net/) and [Lmod](https://lmod.readthedocs.io/en/latest/index.html)

- Lmod uses the Lua, while Environment Modules uses Tcl module scripts
- They have the same usage:
  - `module use /somewhere/modulefiles` use custom modulefiles
    - modulefile's content starts with `#%Module1.0`
    - Lmod filename ends with `.lua`
  - `module avail [name]` check all modules, name is optional
  - `module load cellranger/8.0.1`
  - `module unload cellranger/8.0.1`
  - `module purge` unload all modules

For example, to use the built cellranger modulefile:

```bash
modue load cellranger/9.0.1
# or
ml cellranger/9.0.1
```

Then the `cellranger` command will be available in the `$PATH`.

## Template Modulefiles

### apps/ref-template

[apps-template](apps-template) and [ref-template](ref-template)

- A Tcl script to modify the environment variables when loading/unloading the module
- `[info script]` to get the modulefile path
- Then use tcl functions and regex to retrieve variables from the path
- Set environment variables like `PATH` using `prepend-path` and `setenv`
- `conflict` to avoid loading multiple versions of the same app

### apps/ref-template.lua

[apps-template.lua](apps-template.lua) and [ref-template.lua](ref-template.lua)

- A Lua script to modify the environment variables when loading/unloading the module
- `myFileName()` and `myModuleFullName()` to get the modulefile path and name
- Then use Lua string functions and patterns to retrieve variables from the path
- Edit environment variables like `PATH` using `prepend_path()` and `setenv()`
- `conflict()` to avoid loading multiple versions of the same app

### apps-template(.lua)

| Variable | Description | Example |
| -------- | ----------- | ------- |
| `module_root` | Module root absolute path | `/path/to/modules` |
| `app_root` | Target app absolute path | `/path/to/cellranger/9.0.1` |
| `app_full_name` | Module full name | `cellranger/9.0.1` |
| `app_name` | App name | `cellranger` |
| `app_version` | App version | `9.0.1` |

### refs-template(.lua)

| Variable | Description | Example |
| -------- | ----------- | ------- |
| `module_root` | Module root absolute path | `/path/to/modules` |
| `ref_root` | Target ref absolute path | `/path/to/grch38/genome/gencode` |
| `ref_full_name` | Module full name | `grch38/genome/gencode` |
| `assembly` | Assembly | `grch38` |
| `data_type` | Data type | `genome` |
| `version` | data version | `gencode` |

## apps modules

### apps build scripts

The apps build scripts are named as `build-scripts/name/version`

To use it:

```bash
# under modules folder
./build-scripts/cellranger/9.0.1 -i   # install cellranger 9.0.1
./build-scripts/cellranger/9.0.1 -d   # delete
./build-scripts/cellranger/9.0.1 -u   # update
```

If you want to build your own app, you can check the [apps build script example](#apps-build-script-example) section.

### apps directory structure

```
apps
├── bcftools
│   └── 1.22
├── cellranger
│   └── 9.0.1
├── custom-scripts
│   └── mapping
├── htslib
│   └── 1.22.1
├── samtools
│   └── 1.22.1
├── seqtk
│   └── 1.5
└── star
    └── 2.7.11b
```

### apps module usage

When loading the app modulefile, the app's `bin/` folder will be added to the `PATH`.

```$bash
$ module load cellranger/9.0.1
[2025-11-27 12:54:01] Loading module cellranger/9.0.1

# then the cellranger command is available
$ cellranger --version
cellranger cellranger-9.0.1
```

## apps build script example

[orad/2.7.0](orad/2.7.0)

```bash
#!/usr/bin/bash
#WHATIS:Illumina ORA Decompressor
#URL:https://support.illumina.com/sequencing/sequencing_software/DRAGENORA/software-downloads.html

install_app() {
    # By default, $target_dir and $tmp_dir are created and we are now in $tmp_dir
    url="https://s3.amazonaws.com/webdata.illumina.com/downloads/software/dragen-decompression/orad.${version}.linux.tar.gz"
    wget -nv -O "${app_name}_${version}.tar.gz" "$url"
    tar_xf_pigz "${app_name}_${version}.tar.gz" -C "$target_dir" --strip-components=1

    mkdir -p "$target_dir/bin" # modules/apps/name/version/bin
    mv "$target_dir/orad" "$target_dir/bin"
}

special_modulefiles() {
    # Any additional modulefile operations: add environment variables, aliases, etc.
    # app_root is a special variable that points to the app directory in modulefile[.lua]
    print_stderr "Adding ${BLUE}ORA_REF_PATH${NC} environment variable"
    echo "setenv ORA_REF_PATH \$app_root/oradata" >> "${script_path}"
    echo "setenv(\"ORA_REF_PATH\", pathJoin(app_root, 'oradata'))" >> "${script_path}.lua"
}
```

> [!NOTE]
> By default, the `$target_dir` (`apps/name/version`) and `$tmp_dir` (`tmp/name/version`) are created.
>
> And in the `install_app()` function, we are in `$tmp_dir`.

### What does each section do?

1. `#WHATIS:` and `#URL:` lines are used to replace modulefile's `${WHATIS}` and `${HELP}` placeholders.
2. the script will source the [common.sh](common.sh) file to use common functions and variables.
3. If there are `#DEPENDENCY:` lines, the dependencies will be installed and loaded before running `install_app()`.
4. `install_app()` function is where the app is downloaded and installed to `$target_dir`.
5. then the modulefiles will be copied to `${script_path}(.lua)` files.
6. If `#DEPENDENCY:` lines are present, the dependencies will be added to the modulefiles.
7. `special_modulefiles()` function is optional. It is used to add additional environment variables, aliases, etc. to the modulefile.
8. Results:
   - Successful build: `$tmp_dir` will be removed
   - Failed build: `$target_dir` and `${script_path}(.lua)` files will be removed

Please go to [common.sh](#commonsh) section to learn more about common variables and functions.

### WHATIS and URL

`whatis` is a special command in environment modules to show a brief description of the module.

```
$ module whatis orad/2.7.0
orad/2.7.0: Illumina ORA Decompressor
```

`help` command shows more detailed information about the module. But in my scripts, I only put the URL link to the software page.

```
$ module whatis orad/2.7.0
-------------------------------------------------------------------
Module Specific Help for /opt/modules/apps_modulefiles/orad/2.7.0:

WEBSITE: https://support.illumina.com/sequencing/sequencing_software/DRAGENORA/software-downloads.html
-------------------------------------------------------------------
```

### Dependencies

If the app requires dependencies, you can add them in the build script header.

e.g. [fastqc/0.12.1](../backup/build-scripts/fastqc/0.12.1)

```
#DEPENDENCY:jdk/*
```

- The script will try to query the latest version of `jdk` module and add it to the modulefiles.
- If the version is specified, e.g. `#DEPENDENCY:jdk/11.0.2`, that version will be used. You can also use `jdk/21*` to match the latest version starting with `21`.

### Custom Template Modulefiles

If `template(.lua)` files are not enough, you can create your own modulefiles in the `apps/` folder.

e.g. if `apps/cellranger/modulefile(.lua)` exists, it will be used instead of the template files.

### apps special_modulefiles

The `special_modulefiles()` function is optional. It is used to add additional environment variables, aliases, etc. to the modulefile.

e.g. in [orad/2.7.0](orad/2.7.0), the `ORA_REF_PATH` environment variable is added to point to the reference data folder.

Please go to [apps-template(.lua)](#apps-templatelua) for available variables.

## ref modules

### ref build scripts

The ref build scripts are named as `build-scripts/assembly/data-type/version`

To use it:

```bash
# under modules folder

# install GRCh38 GENCODE genome fasta
./build-scripts/grch38/genome/gencode -i

# delete GRCh38 GENCODE genome fasta
./build-scripts/grch38/genome/gencode -d

# update GRCh38 GENCODE genome fasta
./build-scripts/grch38/genome/gencode -u
```

If you want to build your own reference, you can check the [ref build script example](#ref-build-script-example) section.

### ref directory structure

```
ref
├── grch38
│   ├── cellranger
│   │   └── 2024-A
│   ├── genome
│   │   └── gencode
│   ├── gtf
│   │   └── gencode47
│   ├── rmsk
│   │   └── ucsc
│   └── star-2.7.11b
│       ├── cellranger-2024-A
│       └── gencode47-101
└── grcm39
    └── cellranger
        └── 2024-A
```

To avoid reload, 3 levels of directories are used: `assembly/data-type/version`

For example

```
ml grch38/genome-gencode
ml grch38/transcript-gencode47
```

`lmod` will treat `genome` and `transcript` are different versions, so both modules can NOT be loaded at the same time. To avoid this, we can use `genome/gencode` and `transcript/gencode47` instead.

### ref module usage

When loading the genome reference modulefile, the alignment or related tools will not be loaded automatically. You need to load them separately.

And when loading the reference modulefile, the env variables will be printed when using the terminal (if not running inside a SLURM job).

```
$ module load grch38/cellranger/2024-A
[2025-11-19 15:33:35] Loading module grch38/cellranger/2024-A
Available environment variables:
  CELLRANGER_REF_DIR (reference directory: cellranger)
  GENOME_FASTA       (fasta file)
  ANNOTATION_GTF_GZ  (annotation gtf.gz: gene counting)
  STAR_INDEX_DIR     (star index: star alignment)
```

Then you can use the env variables in your analysis pipelines.

```bash
ml purge
ml cellranger/9.0.1
ml grch38/cellranger/2024-A

cellranger count \
  --id=sample1 \ 
  --transcriptome=$CELLRANGER_REF_DIR \ 
  ...
```

## ref build script example

[grch38/star-2.7.11b/gencode44-101](grch38/star-2.7.11b/gencode44-101)

```bash
#!/usr/bin/bash
#DEPENDENCY:grch38/genome/gencode
#DEPENDENCY:grch38/gtf/gencode44
#DEPENDENCY:star/2.7.11b
#WHATIS:STAR GRCh38 GENCODE44 index for read length 101
#URL:https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf

install_app() {
    # By default, $target_dir and $tmp_dir are created and we are now in $tmp_dir
    pigz_or_gunzip_pipe "$ANNOTATION_GTF_GZ" > annotation.gtf
    
    print_stderr "Building STAR index for ${YELLOW}${app_name_version}${NC}"
    STAR --runThreadN $ncpu \
        --runMode genomeGenerate \
        --genomeDir "$target_dir" \
        --genomeFastaFiles "$GENOME_FASTA" \
        --sjdbGTFfile annotation.gtf \
        --sjdbOverhang 100
}

special_modulefiles() {
    # Any additional modulefile operations: add environment variables, aliases, etc.
    # ref_root is a special variable that points to the ref directory in modulefile[.lua]
    cat << EOF >> "${script_path}"
set star_index_dir \$ref_root
setenv STAR_INDEX_DIR \$star_index_dir
if { [module-info mode] == "load" && ![info exists ::env(SLURM_JOB_ID)] } {
    puts stderr "Available environment variables:"
    puts stderr "  STAR_INDEX_DIR   (STAR index directory: star alignment)"
}
EOF

    cat << EOF >> "${script_path}.lua"
local star_index_dir = ref_root
setenv("STAR_INDEX_DIR", star_index_dir)
if (mode() == "load" and os.getenv("SLURM_JOB_ID") == nil) then
    io.stderr:write("Available environment variables:\n")
    io.stderr:write("  STAR_INDEX_DIR   (STAR index directory: star alignment)\n")
end
EOF
}
```

### What does each section do?

1. `#WHATIS:` and `#URL:` lines are used to replace modulefile's `${WHATIS}` and `${HELP}` placeholders.
2. the script will source the [common.sh](common.sh) file to use common functions and variables.
3. If there are `#DEPENDENCY:` lines, the dependencies will be installed and loaded before running `install_app()`.
4. `install_app()` function is where the reference data is built and installed to `$target_dir`.
5. then the modulefiles will be copied to `${script_path}(.lua)` files.
6. The dependencies will be added to the modulefiles.
7. `special_modulefiles()` function is optional. It is used to add additional environment variables, aliases, etc. to the modulefile.
8. Results:
   - Successful build: `$tmp_dir` will be removed
   - Failed build: `$target_dir` and `${script_path}(.lua)` files will be removed

Please go to [common.sh](#commonsh) section to learn more about common variables and functions.

### WHATIS and URL

`whatis` is a special command in environment modules to show a brief description of the module.

```$ module whatis star-2.7.11b/gencode44-101
star-2.7.11b/gencode44-101: STAR GRCh38 GENCODE44 index for read length 101
```

`help` command shows more detailed information about the module. But in my scripts, I only put the URL link to the software page.

```$ module help star-2.7.11b/gencode44-101
-------------------------------------------------------------------
Module Specific Help for /opt/modules/refs_modulefiles/grch38/star-2.7.11b/gencode44-101:

WEBSITE: https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf
-------------------------------------------------------------------
```

### Dependencies

If the reference requires dependencies, you can add them in the build script header.

e.g. in [grch38/star-2.7.11b/gencode44-101](grch38/star-2.7.11b/gencode44-101)

```
#DEPENDENCY:grch38/genome/gencode
#DEPENDENCY:grch38/gtf/gencode44
#DEPENDENCY:star/2.7.11b
```

- The script will try to install and load the dependencies before running `install_app()`.
- If the version is specified, that version will be used. You can also use wildcards to match the latest version.

But for references, it is recommended to specify the exact version to avoid unexpected changes, like STAR index may not be compatible between different STAR versions.

### Custom Template Modulefiles

If `template(.lua)` files are not enough, you can create your own modulefiles in the `refs/` folder.

e.g. if `refs/grch38/star/modulefile(.lua)` exists, it will be used instead of the template files.

### refs special_modulefiles

The `special_modulefiles()` function is optional. It is used to add additional environment variables, aliases, etc. to the modulefile.

e.g. in [grch38/star-2.7.11b/gencode44-101](grch38/star-2.7.11b/gencode44-101), the `STAR_INDEX_DIR` environment variable is added to point to the STAR index directory.

Also to print available environment variables when loading the module (if not in a SLURM job).

Please go to [refs-template(.lua)](#refs-templatelua) for available variables.

To learn more about modulefiles, please go to [Environment Modules and Lmod](#environment-modules-and-lmod).

## common.sh

The `common.sh` file contains common functions and variables used in the build scripts.

| Variable | Description |
| -------- | ----------- |
| `ncpu` | Number of CPUs to use (default: env `SLURM_CPUS_PER_TASK` or 4) |
| `app_name` | apps: app name; ref: assembly/data-type |
| `version` | apps: app version; ref: data version |
| `target_dir` | Target installation directory (`apps/name/version` or `ref/assembly/data-type/version`) |
| `script_path` | Modulefile path (`apps_modulefiles/name/version` or `ref_modulefiles/assembly/data-type/version`) |
| `tmp_dir` | Temporary working directory (`tmp/name/version`) |

| Function | Description |
| -------- | ----------- |
| `print_stderr` | Print message to stderr |
| `pigz_or_gunzip` | Decompress gz file using pigz or gunzip |
| `tar_xf_pigz` | Extract tar.gz using pigz if available |
| `pigz_or_gunzip_pipe` | Decompress gz file and pipe to stdout using pigz or gunzip |
