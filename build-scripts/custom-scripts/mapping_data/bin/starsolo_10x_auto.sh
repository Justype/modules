#!/bin/bash -e 

## Adapted from https://github.com/cellgeni/STARsolo
## v3.2 of STARsolo wrappers is set up to guess the chemistry automatically
## newest version of the script uses STAR v2.7.10a with EM multimapper processing 
## in STARsolo which on by default; the extra matrix can be found in /raw subdir

print_help() {
  echo "Usage: $0 -i <fastq_dir> -s <sample_id> -r <reference_dir> [-t <threads>] [-o <output_dir>] [-n]"
  echo ""
  echo "This script automatically detects 10x chemistry version and runs STARsolo accordingly."
  echo "The output will be in the <output_dir>/<sample_id>/ directory."
  echo ""
  echo "Arguments:"
  echo "  -i    fastq directory containing FASTQ files"
  echo "  -s    sample ID (used to identify FASTQ files)"
  echo "  -r    STAR reference directory"
  echo "  -t    number of threads (default: 16)"
  echo "  -o    output directory (default: current directory)"
  echo "  -n    no BAM output (default: output)"
  echo "  -h    display this help message"
}

NO_BAM=false
OUTPUT_DIR="."

while getopts i:s:r:t:o:n:h flag; do
    case "${flag}" in
        i) FQDIR=${OPTARG};;   # input fastq dir
        s) TAG=${OPTARG};;     # sample id
        r) REF=${OPTARG};;     # reference dir
        t) CPUS=${OPTARG};;    # number of threads
        o) OUTPUT_DIR=${OPTARG};; # output directory
        n) NO_BAM=true;;    # no BAM output
        h) 
           print_help
           exit 0;;
    esac
done

CPUS=${CPUS:-16}            # default to 16 threads if not specified

if [[ -z "$FQDIR" || -z "$TAG" || -z "$REF" ]]; then
    echo "ERROR: Missing required arguments."
    print_help
    exit 1
fi

# absolute path for FQDIR and REF
FQDIR=$(readlink -f "$FQDIR")
REF=$(readlink -f "$REF")

# Check if barcode files are available in environment variables; if not exit with error
module load data-utils/cellranger/9.0.1-barcodes
if [[ -z "$BARCODE_3PV1" || -z "$BARCODE_3PV2" || -z "$BARCODE_3PV3" || -z "$BARCODE_3PV4" || -z "$BARCODE_5PV3" || -z "$BARCODE_ARCV1" ]]; then
    echo "ERROR: Barcode files not found in environment variables."
    echo "Please install and load the data-utils/cellranger/9.0.1-barcodes module."
    exit 1
fi

for app in seqtk STAR samtools; do
  if ! command -v $app &> /dev/null; then
    echo "ERROR: $app not found in PATH. Please load the appropriate module, use conda env, or singularity."
    exit 1
  fi
done

if [ "$NO_BAM" = true ] ; then
  BAM="--outSAMtype None --outReadsUnmapped Fastx"
else
  BAM="--outSAMtype BAM SortedByCoordinate --outBAMsortingBinsN 500 --limitBAMsortRAM 60000000000 --outSAMunmapped Within --outMultimapperOrder Random --runRNGseed 1 --outSAMattributes NH HI AS nM CB UB CR CY UR UY GX GN"
fi

###################################################################### DONT CHANGE OPTIONS BELOW THIS LINE ##############################################################################################

mkdir -p $OUTPUT_DIR && cd $OUTPUT_DIR
mkdir -p $TAG && cd $TAG

## four popular cases: ENA - <sample>_1.fastq/<sample>_2.fastq, regular - <sample>.R1.fastq/<sample>.R2.fastq
## Cell Ranger - <sample>_L001_R1_S001.fastq/<sample>_L001_R2_S001.fastq, and HRA - <sample>_f1.fastq/<sample>_r2.fastq
## the command below will generate a comma-separated list for each read if there are >1 file for each mate
## archives (gzip/bzip2) are considered below; both .fastq and .fq should work, too. 
echo [`date +"%Y-%m-%d %T"`] Deteriming input FASTQ files naming convention...
R1=""
R2=""
if [[ `find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_1\.f.*q"` != "" ]]
then 
  R1=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_1\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
  R2=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_2\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
elif [[ `find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "R1\.f.*q"` != "" ]]
then
  R1=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "R1\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
  R2=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "R2\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
elif [[ `find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_R1_.*\.f.*q"` != "" ]]
then
  R1=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_R1_.*\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
  R2=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_R2_.*\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
elif [[ `find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_f1\.f.*q"` != "" ]]
then
  R1=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_f1\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
  R2=`find $FQDIR/* | grep -P "\/$TAG[\/\._]" | grep "_r2\.f.*q" | sort | tr '\n' ',' | sed "s/,$//g"`
else 
  >&2 echo "ERROR: No appropriate fastq files were found! Please check file formatting, and check if you have set the right FQDIR."
  exit 1
fi 

## define some key variables, in order to evaluate reads for being 1) gzipped/bzipped/un-archived; 
## 2) having barcodes from the whitelist, and which; 3) having consistent length; 4) being single- or paired-end. 
GZIP=""
BC=""
NBC1=""
NBC2=""
NBC3=""
NBCA=""
R1LEN=""
R2LEN=""
R1DIS=""
ZCMD="cat"

## see if the original fastq files are archived: 
if [[ `find $FQDIR/* | grep -P "$TAG[\/\._]" | grep "\.gz$"` != "" ]]
then  
  GZIP="--readFilesCommand zcat"
  ZCMD="zcat"
elif [[ `find $FQDIR/* | grep -P "$TAG[\/\._]" | grep "\.bz2$"` != "" ]]
then
  GZIP="--readFilesCommand bzcat"
  ZCMD="bzcat"
fi

## we need a small and random selection of reads. the solution below is a result of much trial and error.
## in the end, we select 200k reads that represent all of the files present in the FASTQ dir for this sample.
## have to use numbers because bamtofastq likes to make files with identical names in different folders..
echo [`date +"%Y-%m-%d %T"`] Generating test FASTQ files for chemistry detection...
COUNT=0
for i in `echo $R1 | tr ',' ' '`
do
  $ZCMD $i | head -4000000 > $COUNT.R1_head &
  COUNT=$((COUNT+1))
done
wait 

COUNT=0
for i in `echo $R2 | tr ',' ' ' `                                                
do 
  $ZCMD $i | head -4000000 > $COUNT.R2_head &
  COUNT=$((COUNT+1))
done
wait

## same random seed makes sure you select same reads from R1 and R2
cat *.R1_head | $CMD seqtk sample -s100 - 200000 > test.R1.fastq &
cat *.R2_head | $CMD seqtk sample -s100 - 200000 > test.R2.fastq &
wait 
rm *.R1_head *.R2_head

## elucidate the right barcode whitelist to use. Grepping out N saves us some trouble. Note the special list for multiome experiments (737K-arc-v1.txt):
## 50k (out of 200,000) is a modified empirical number - matching only first 14-16 nt makes this more specific
echo [`date +"%Y-%m-%d %T"`] Detecting 10X chemistry version...
NBC1=`cat test.R1.fastq | awk 'NR%4==2' | cut -c-14 | grep -F -f $BARCODE_3PV1 | wc -l`
NBC2=`cat test.R1.fastq | awk 'NR%4==2' | cut -c-16 | grep -F -f $BARCODE_3PV2 | wc -l`
NBC3=`cat test.R1.fastq | awk 'NR%4==2' | cut -c-16 | grep -F -f $BARCODE_3PV3 | wc -l`
NBC4=`cat test.R1.fastq | awk 'NR%4==2' | cut -c-16 | grep -F -f $BARCODE_3PV4 | wc -l`
NBC5=`cat test.R1.fastq | awk 'NR%4==2' | cut -c-16 | grep -F -f $BARCODE_5PV3 | wc -l`
NBCA=`cat test.R1.fastq | awk 'NR%4==2' | cut -c-16 | grep -F -f $BARCODE_ARCV1 | wc -l`
R1LEN=`cat test.R1.fastq | awk 'NR%4==2' | awk '{sum+=length($0)} END {printf "%d\n",sum/NR+0.5}'`
R2LEN=`cat test.R2.fastq | awk 'NR%4==2' | awk '{sum+=length($0)} END {printf "%d\n",sum/NR+0.5}'`
R1DIS=`cat test.R1.fastq | awk 'NR%4==2' | awk '{print length($0)}' | sort | uniq -c | wc -l`

if (( $NBC3 > 50000 )) 
then 
  BC=$BARCODE_3PV3
elif (( $NBC2 > 50000 ))
then
  BC=$BARCODE_3PV2
elif (( $NBCA > 50000 ))
then
  BC=$BARCODE_ARCV1
elif (( $NBC1 > 50000 )) 
then
  BC=$BARCODE_3PV1
elif (( $NBC4 > 50000 )) 
then
  BC=$BARCODE_3PV4
elif (( $NBC5 > 50000 )) 
then
  BC=$BARCODE_5PV3
else 
  >&2 echo "ERROR: No whitelist has matched a random selection of 200,000 barcodes! Match counts: $NBC1 (v1), $NBC2 (v2), $NBC3 (v3), $NBC4 (v4-3p), $NBC5 (v3-5p), $NBCA (multiome)."
  exit 1
fi 

## check read lengths, fail if something funky is going on: 
PAIRED=False
UMILEN=""
CBLEN=""
if (( $R1DIS > 1 && $R1LEN <= 30 ))
then 
  >&2 echo "ERROR: Read 1 (barcode) has varying length; possibly someone thought it's a good idea to quality-trim it. Please check the fastq files."
  exit 1
elif (( $R1LEN < 24 )) 
then
  >&2 echo "ERROR: Read 1 (barcode) is less than 24 bp in length. Please check the fastq files."
  exit 1
elif (( $R2LEN < 40 )) 
then
  >&2 echo "ERROR: Read 2 (biological read) is less than 40 bp in length. Please check the fastq files."
  exit 1
fi

## assign the necessary variables for barcode/UMI length/paired-end processing. 
## script was changed to not rely on read length for the UMIs because of the epic Hassan case
# (v2 16bp barcodes + 10bp UMIs were sequenced to 28bp, effectively removing the effects of the UMIs)
if (( $R1LEN > 50 )) 
then
  PAIRED=True
fi

if [[ $BC == "$BARCODE_3PV3" || $BC == "$BARCODE_ARCV1" || $BC == "$BARCODE_3PV4" || $BC == "$BARCODE_5PV3" ]] 
then 
  CBLEN=16
  UMILEN=12
elif [[ $BC == "$BARCODE_3PV2" ]] 
then
  CBLEN=16
  UMILEN=10
elif [[ $BC == "$BARCODE_3PV1" ]] 
then
  CBLEN=14
  UMILEN=10
fi

case $BC in
  "$BARCODE_3PV1")  CHEM="3 prime v1";;
  "$BARCODE_3PV2")  CHEM="3 prime v2";;
  "$BARCODE_3PV3")  CHEM="3 prime v3";;
  "$BARCODE_3PV4")  CHEM="3 prime v4";;
  "$BARCODE_5PV3")  CHEM="5 prime v3";;
  "$BARCODE_ARCV1") CHEM="ATAC + RNA";;
esac

echo [`date +"%Y-%m-%d %T"`] Detected chemistry: $CHEM

## yet another failsafe! Some geniuses managed to sequence v3 10x with a 26bp R1, which also causes STARsolo grief. This fixes it.
if (( $CBLEN + $UMILEN > $R1LEN ))
then
  NEWUMI=$((R1LEN-CBLEN))
  BCUMI=$((UMILEN+CBLEN))
  >&2 echo "WARNING: Read 1 length ($R1LEN) is less than the sum of appropriate barcode and UMI ($BCUMI). Changing UMI setting from $UMILEN to $NEWUMI!"
  UMILEN=$NEWUMI
elif (( $CBLEN + $UMILEN < $R1LEN ))
then
  BCUMI=$((UMILEN+CBLEN))
  >&2 echo "WARNING: Read 1 length ($R1LEN) is more than the sum of appropriate barcode and UMI ($BCUMI)."
fi

## it's hard to come up with a universal rule to correctly infer strand-specificity of the experiment. 
## this is the best I could come up with: 1) check if fraction of test reads (200k random ones) maps to GeneFull forward strand 
## with higher than 50% probability; 2) if not, run the same quantification with "--soloStand Reverse" and calculate the same stat; 
## 3) output a warning, and choose the strand with higher %; 4) if both percentages are below 10, 
echo [`date +"%Y-%m-%d %T"`] Determining strand info by test mapping...
STRAND=Forward

echo [`date +"%Y-%m-%d %T"`] Testing Forward strand mapping...
$CMD STAR --runThreadN $CPUS --genomeDir $REF --readFilesIn test.R2.fastq test.R1.fastq --runDirPerm All_RWX --outSAMtype None \
     --soloType CB_UMI_Simple --soloCBwhitelist $BC --soloBarcodeReadLength 0 --soloCBlen $CBLEN --soloUMIstart $((CBLEN+1)) \
     --soloUMIlen $UMILEN --soloStrand Forward --genomeLoad LoadAndKeep \
     --soloUMIdedup 1MM_CR --soloCBmatchWLtype 1MM_multi_Nbase_pseudocounts --soloUMIfiltering MultiGeneUMI_CR \
     --soloCellFilter EmptyDrops_CR --clipAdapterType CellRanger4 --outFilterScoreMin 30 \
     --soloFeatures Gene GeneFull --soloOutFileNames test_forward/ features.tsv barcodes.tsv matrix.mtx &> test_forward.log

if [ $? -ne 0 ]; then
  >&2 echo "ERROR: STAR failed during forward strand test mapping! Check test_forward.log for details."
  exit 1
fi

echo [`date +"%Y-%m-%d %T"`] Testing Reverse strand mapping...
$CMD STAR --runThreadN $CPUS --genomeDir $REF --readFilesIn test.R2.fastq test.R1.fastq --runDirPerm All_RWX --outSAMtype None \
     --soloType CB_UMI_Simple --soloCBwhitelist $BC --soloBarcodeReadLength 0 --soloCBlen $CBLEN --soloUMIstart $((CBLEN+1)) \
     --soloUMIlen $UMILEN --soloStrand Reverse --genomeLoad LoadAndKeep \
     --soloUMIdedup 1MM_CR --soloCBmatchWLtype 1MM_multi_Nbase_pseudocounts --soloUMIfiltering MultiGeneUMI_CR \
     --soloCellFilter EmptyDrops_CR --clipAdapterType CellRanger4 --outFilterScoreMin 30 \
     --soloFeatures Gene GeneFull --soloOutFileNames test_reverse/ features.tsv barcodes.tsv matrix.mtx &> test_reverse.log

if [ $? -ne 0 ]; then
  >&2 echo "ERROR: STAR failed during reverse strand test mapping! Check test_reverse.log for details."
  exit 1
fi

echo [`date +"%Y-%m-%d %T"`] Calculating mapping percentages...

PCTFWD=`grep "Reads Mapped to GeneFull: Unique GeneFull" test_forward/GeneFull/Summary.csv | awk -F "," '{printf "%d\n",$2*100+0.5}'`
PCTREV=`grep "Reads Mapped to GeneFull: Unique GeneFull" test_reverse/GeneFull/Summary.csv | awk -F "," '{printf "%d\n",$2*100+0.5}'`

if (( $PCTREV > $PCTFWD )) 
then
  STRAND=Reverse
fi

if (( $PCTREV < 50 && $PCTFWD < 50)) 
then
  >&2 echo "WARNING: Low percentage of reads mapping to GeneFull: forward = $PCTFWD , reverse = $PCTREV"
fi 

## finally, if paired-end experiment turned out to be 3' (yes, they do exist!), process it as single-end: 
if [[ $STRAND == "Forward" && $PAIRED == "True" ]]
then
  PAIRED=False
fi

## write a file in the sample dir too, these metrics are not crucial but useful 
echo "[`date +'%Y-%m-%d %T'`] Done setting up the STARsolo run; here are final processing options:"
echo "============================================================================="
echo "Sample: $TAG" | tee strand.txt
echo "Detected Chemistry: $CHEM" | tee -a strand.txt
echo "Paired-end mode: $PAIRED" | tee -a strand.txt
echo "Strand (Forward = 3', Reverse = 5'): $STRAND" | tee -a strand.txt
echo "CB whitelist: $BC" | tee -a strand.txt
echo "-----------------------------------------------------------------------------" | tee -a strand.txt
echo "Matches out of 200,000:" | tee -a strand.txt
echo "    3 prime v1: $NBC1" | tee -a strand.txt
echo "    3 prime v2: $NBC2" | tee -a strand.txt
echo "    3 prime v3: $NBC3" | tee -a strand.txt
echo "    3 prime v4: $NBC4" | tee -a strand.txt
echo "    5 prime v3: $NBC5" | tee -a strand.txt
echo "    ATAC + RNA: $NBCA" | tee -a strand.txt
echo "-----------------------------------------------------------------------------" | tee -a strand.txt
echo "%reads mapped to GeneFull in test mapping:" | tee -a strand.txt
echo "    Forward strand: $PCTFWD" | tee -a strand.txt
echo "    Reverse strand: $PCTREV" | tee -a strand.txt
echo "-----------------------------------------------------------------------------" | tee -a strand.txt
echo "CB length: $CBLEN" | tee -a strand.txt
echo "UMI length: $UMILEN" | tee -a strand.txt
echo "GZIP: $GZIP" | tee -a strand.txt
echo "-----------------------------------------------------------------------------" | tee -a strand.txt
echo "Read 1 files: $R1" | tee -a strand.txt
echo "Read 2 files: $R2" | tee -a strand.txt
echo "-----------------------------------------------------------------------------" | tee -a strand.txt

if [[ $PAIRED == "True" ]]
then
  ## note the R1/R2 order of input fastq reads and --soloStrand Forward for 5' paired-end experiment
  $CMD STAR --runThreadN $CPUS --genomeDir $REF --readFilesIn $R1 $R2 --runDirPerm All_RWX $GZIP $BAM --soloBarcodeMate 1 --clip5pNbases 39 0 \
     --soloType CB_UMI_Simple --soloCBwhitelist $BC --soloCBstart 1 --soloCBlen $CBLEN --soloUMIstart $((CBLEN+1)) --soloUMIlen $UMILEN --soloStrand Forward \
     --soloUMIdedup 1MM_CR --soloCBmatchWLtype 1MM_multi_Nbase_pseudocounts --soloUMIfiltering MultiGeneUMI_CR \
     --soloCellFilter EmptyDrops_CR --outFilterScoreMin 30 --genomeLoad LoadAndRemove \
     --soloFeatures Gene GeneFull Velocyto SJ --soloOutFileNames output/ features.tsv barcodes.tsv matrix.mtx --soloMultiMappers EM
else 
  $CMD STAR --runThreadN $CPUS --genomeDir $REF --readFilesIn $R2 $R1 --runDirPerm All_RWX $GZIP $BAM \
     --soloType CB_UMI_Simple --soloCBwhitelist $BC --soloBarcodeReadLength 0 --soloCBlen $CBLEN --soloUMIstart $((CBLEN+1)) --soloUMIlen $UMILEN --soloStrand $STRAND \
     --soloUMIdedup 1MM_CR --soloCBmatchWLtype 1MM_multi_Nbase_pseudocounts --soloUMIfiltering MultiGeneUMI_CR \
     --soloCellFilter EmptyDrops_CR --clipAdapterType CellRanger4 --outFilterScoreMin 30 --genomeLoad LoadAndRemove \
     --soloFeatures Gene GeneFull Velocyto SJ --soloOutFileNames output/ features.tsv barcodes.tsv matrix.mtx --soloMultiMappers EM
fi

## index the BAM file
if [[ -s Aligned.sortedByCoord.out.bam ]]
then
  $CMD samtools index -@ $CPUS Aligned.sortedByCoord.out.bam
fi

# ## gzip the unmapped reads
# pigz -p $CPUS Unmapped.out.mate1
# pigz -p $CPUS Unmapped.out.mate2

## remove test files 
echo [`date +"%Y-%m-%d %T"`] Cleaning up temporary files...
rm -rf test*
rm -rf _STARtmp

echo [`date +"%Y-%m-%d %T"`] Compressing output matrices...
# SJ/raw/features.tsv is a abs symlink to SJ.out.tab; which is not safe if we copy/move the output dir
find output -name '*.tsv' -exec sh -c '
  pigz -p "$0" "$1" -c > "$1.gz" && rm "$1"
' "$CPUS" {} \;
pigz -p $CPUS output/*/*/*.mtx

echo "ALL DONE!"
