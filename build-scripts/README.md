# Package Notes

## Environment Modules and Lmod

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

## BCFtools

[BCFtools Howtos](https://samtools.github.io/bcftools/howtos/index.html)

BCFtools's plugins are under `bcftools/version/libexec/bcftools`. You need to set `$BCFTOOLS_PLUGINS` to that directory so that BCFtools can find the plugins.

e.g. `setenv BCFTOOLS_PLUGINS "$app_root/libexec/bcftools"` in `modulefiles/bcftools/version`

## Cell Ranger

Since the link from 10X is only valid for **one** day, you will need to change the link to make it work.

In `cellranger/x.y.z` line 127:

```bash
run_command wget -O cellranger-9.0.0.tar.gz "https://cf.10xgenomics.com/releases/cell-exp/cellranger-9.0.0.tar.gz"
```

Go to 10X and get the link: https://www.10xgenomics.com/support/software/cell-ranger/downloads/previous-versions

## GATK

GATK requires Java Environment to run. So In the building script, the latest jdk in my list will be downloaded. And the modulefiles also be edited to load jdk.

e.g. `load jdk/latest_version` in `modulefiles/gatk/version`

## GDC-Client

[GDC client](https://gdc.cancer.gov/access-data/gdc-data-transfer-tool) is used to transfer data from/to Genomic Data Commons.

Version `2.x.x` requires `glibc 2.29` to run. If the `glibc` on your machine is below `2.29`, install version `1.6.1`.

Use `ldd --version` to get `glibc` version.

## ORAD (ORA Decompress Tool)

According to [Illumina instruction](https://help.ora.illumina.com/product-guides/dragen-ora-decompression/software-installation), `orad` needs `$ORA_REF_PATH/refbin` to decompress. So My script edit the `ORA_REF_PATH` env variable.

## Picard

[Picard](https://broadinstitute.github.io/picard/) is a `jar` not a program. Set `PICARD` env to the path of `jar`. And use `alias picard='java -jar $PICARD'` to set `picard` alias.
