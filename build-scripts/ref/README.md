# Genome Reference Build Scripts

My goal is to save disk space by sharing genome reference files among different software tools. Symlinks are used to link the same reference files to different software tools.

- use modules can skip the path issue, or you can use symlink
- modulefiles will be under `modules/modulefiles/ref/`
- genome reference files will be under `modules/ref/`
- When you load a reference module, it will also load the corresponding software modules.

structure:

- ref
  - data: genome reference and annotation files
    - genome: GRCh38, T2T-CHM13, GRCm39
      - annotation: GENCODE38, GENCODE47
  - apps: index files for that apps
    - version: version of the app when build the index (does it necessary?)
      - genome: which genome is used
        - annotation: which annotation is used

## Ideal structure

- data: genome reference and annotation files
  - GRCh38
    - GENCODE38
    - GENCODE47
  - T2T-CHM13
  - GRCm39
- bwa
- bowtie2
- cellranger
- hisat2
- star
- kallisto
- minimap2
- vg
