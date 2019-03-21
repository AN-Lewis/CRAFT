#!/usr/bin/env python
#
# Main CRAFT program

import sys
import os
import argparse
import glob

import pandas as pd

from craft import config
from craft import read
from craft import abf
from craft import annotate
from craft import finemap
from craft import log
import craft.getSNPs as gs

# All file reading functions. Each takes a file name and returns a DataFrame.
readers = {'snptest': read.snptest,
           'plink': read.plink,
           'plink2': read.plink_noBIM,
           'indexsnps': read.indexsnps,
           'csv': read.csv,
}

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--file', required=True,
        help='Input summary statistics file. Use * to include multiple files.')
    parser.add_argument(
        '--type', required = True, choices=readers.keys(),
        help='Define input file type.')
    # parser.add_argument(
    #    '--bim', action='store', help='Specify BIM file location (required for plink)')
    parser.add_argument(
        '--out', required=True,
        help='Output file for table of index SNPs with summary statistics.')
    parser.add_argument(
        '--outsf', required=True,
        help='Output file for summary statistics of the credible set.')
    parser.add_argument(
        '--alpha', default=5e-5, type=float,
        help='P-value threshold for declaring index SNPs. Default = %(default)s.')
    parser.add_argument(
        '--distance_unit', choices=['cm','bp'], default = 'cm',
        help='Choose the distance unit (for use in defining regions). Default = %(default)s.')
    parser.add_argument(
        '--distance', default='0.1',
        help='Define distance around index SNP by base-pair or cM. e.g. 500000 for bp or 0.1 for cM. Default = %(default)s.')
    parser.add_argument(
        '--mhc', action='store_true',
        help='Include the MHC region. Default = %(default)s.')
    parser.add_argument(
        '--finemap_tool', choices={'caviar','cojo', 'finemap', 'paintor'},
        help='Choose which finemap tool is used. Default = %(default)s.')
    return parser.parse_args()

def main():
    options = parse_args() # Define command-line specified options
    file_names = glob.glob(options.file)
    if not file_names:
        log.error('Error: file not found!')
    reader = readers[options.type]
    stats = [reader(n) for n in file_names] # Read input summary statistics

    if options.distance_unit == 'cm': # Get index SNPs using cm as distance
        distance = float(options.distance)
        maps = read.maps(config.genetic_map_dir)
        index_dfs = [gs.get_index_snps_cm(d, options.alpha, distance, options.mhc, maps) for d in stats]
    if options.distance_unit == 'bp': # Get index SNPs using bp as distance
        distance = int(options.distance)
        index_dfs = [gs.get_index_snps_bp(d, options.alpha, distance, options.mhc) for d in stats]
    index_df = pd.concat(index_dfs)
    index_df = annotate.prepare_df_annoVar(index_df)
    index_df = annotate.base_annotation_annoVar(index_df) # Annotate index SNPs
    out_file = options.out
    # Output index SNPs
    index_df.to_csv(out_file, sep='\t', float_format='%5f', index=False)

    # Calculate ABF and posterior probabilities
    for stat_df in stats:
        data = gs.get_locus_snps(stat_df, index_df)
    data['ABF'] = data.apply(
        lambda row: abf.calc_abf(pval=row['pvalue'],
                                maf=row['all_maf'],
                                n=row['all_total'],
                                n_controls=row['controls_total'],
                                n_cases=row['cases_total']), axis=1)
    data = data.sort_values('ABF', ascending=False)
    data = annotate.prepare_df_annoVar(data)
    data = annotate.base_annotation_annoVar(data) # Annotate credible SNPs
    # Output credible SNP set
    data.to_csv(options.outsf, sep='\t', float_format='%5f', index=False)

    if options.finemap_tool:
        finemap.open()
    return 0
