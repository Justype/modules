# Build Scripts

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
2. run build scripts, e.g. `bash build-scripts/sra-tools/3.1.1 -d`
   - `-d` for deleting

## Cell Ranger

Since the link from 10X is only valid for **one** day, you will need to change the link to make it work.

In `cellranger/x.y.z` line 104:

```bash
run_command wget -O cellranger-9.0.0.tar.gz "https://cf.10xgenomics.com/releases/cell-exp/cellranger-9.0.0.tar.gz"
```

Go to 10X and get the link: https://www.10xgenomics.com/support/software/cell-ranger/downloads/previous-versions

## GATK

GATK requires Java Environment to run. So In the building script, the latest jdk in my list will be downloaded. And the modulefiles also be edited to load jdk.

e.g. `load jdk/latest_version` in `modulefiles/gatk/version`
