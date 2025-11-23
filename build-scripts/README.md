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

## Genome FASTA/GTF and Indexes

~~The files (FASTA, GTF, indexes, etc.) for genome references are under `ref-<genome_assembly_version>` folders, e.g., `ref-hg19`, `ref-hg38`, `ref-mm10`, `ref-mm39`, etc.~~

The previous structure works fine on environment modules but not on lmod. When loading `ref-grch/gtf` and `ref-grch/fasta`, the latter one will make the former one unload. So I separate modules by data types like: `data-fasta`, `data-gtf`, `data-index` ...

The scripts/modulefiles will be modified to set the env variables to point to the files. e.g. `CELLRANGER_REF_DIR`, `STAR_INDEX_DIR`, `GENOME_FASTA`, etc.

```
build-scripts/data-fasta
├── grch38-genome-gencode
└── grch38-transcript-gencode47
build-scripts/data-gtf
└── grch38-gencode47
build-scripts/data-index
├── cellranger-grch38-2024-A
├── star-grch38-gencode47-101
└── star-grch38-gencode47-151
```

When loading the genome reference modulefile, the alignment or related tools will not be loaded automatically. You need to load them separately.

And when loading the reference modulefile, the env variables will be printed when using the terminal.

```
$ module load data-index/cellranger-grch38-2024-A
[2025-11-19 15:33:35] Loading module data-index/cellranger-grch38-2024-A
Available environment variables:
  CELLRANGER_REF_DIR (reference directory: cellranger)
  GENOME_FASTA       (fasta file)
  ANNOTATION_GTF_GZ  (annotation gtf.gz: gene counting)
  STAR_INDEX_DIR     (star index: star alignment)
```

Then you can use the env variables in your analysis pipelines.

```bash
module load cellranger/9.0.1
module load data-index/cellranger-grch38-2024-A

cellranger count \
  --id=sample1 \ 
  --transcriptome=$CELLRANGER_REF_DIR \ 
  ...
```

## BCFtools

[BCFtools Howtos](https://samtools.github.io/bcftools/howtos/index.html)

BCFtools's plugins are under `bcftools/version/libexec/bcftools`. You need to set `$BCFTOOLS_PLUGINS` to that directory so that BCFtools can find the plugins.

e.g. `setenv BCFTOOLS_PLUGINS "$app_root/libexec/bcftools"` in `modulefiles/bcftools/version`

## Cell Ranger

Since the link from 10X is only valid for **one** day, you will need to change the link to make it work.

In `cellranger/x.y.z` line 127:

```bash
wget -O cellranger-9.0.0.tar.gz "https://cf.10xgenomics.com/releases/cell-exp/cellranger-9.0.0.tar.gz"
```

Go to 10X and get the link: https://www.10xgenomics.com/support/software/cell-ranger/downloads/previous-versions

## GATK

GATK requires Java Environment to run. So In the building script, the latest jdk in my list will be downloaded. And the modulefiles also be edited to load jdk.

e.g. `load jdk/latest_version` in `modulefiles/gatk/version`

## GDC-Client

[GDC client](https://gdc.cancer.gov/access-data/gdc-data-transfer-tool) is used to transfer data from/to Genomic Data Commons.

Version `2.x.x` requires `glibc 2.29` to run. If the `glibc` on your machine is below `2.29`, install version `1.6.1`.

Use `ldd --version` to get `glibc` version.

## KMC (K mer Counter)

[KMC](https://github.com/refresh-bio/KMC) is a disk-based program for counting k-mers from (possibly gzipped) FASTQ/FASTA files.

## ORAD (ORA Decompress Tool)

According to [Illumina instruction](https://help.ora.illumina.com/product-guides/dragen-ora-decompression/software-installation), `orad` needs `$ORA_REF_PATH/refbin` to decompress. So My script edit the `ORA_REF_PATH` env variable.

## Picard

[Picard](https://broadinstitute.github.io/picard/) is a `jar` not a program. Set `PICARD` env to the path of `jar`. And use `alias picard='java -jar $PICARD'` to set `picard` alias.

## Strelka2 Small Variant Caller

[Strelka2](https://github.com/Illumina/strelka) use Python2.
