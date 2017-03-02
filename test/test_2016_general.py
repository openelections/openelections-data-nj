#!/usr/bin/python

import sys
import argparse
import csv
from collections import defaultdict
from nj_common import *

def main():

    args = handle_arguments()
    process_county_file(args, '../2016/20161108__nj__general.csv')
    process_muni_file(args, '../2016/20161108__nj__general__municipal.csv')
    compare_county_and_muni_totals(args, 
                                   '../2016/20161108__nj__general.csv',
                                   '../2016/20161108__nj__general__municipal.csv')

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2016 county and muni data')
    arg_parser.add_argument('--verbose', '-v', dest='verbose',  help='report information verbosely', action='store_true')
    arg_parser.add_argument('--case', '-c', dest='case',  help='case sensitive text compare', action='store_true')
    return arg_parser.parse_args()

def process_county_file(args, in_file):

    error_count = 0

    verifier = VerifyCounty(in_file, args.verbose, args.case)   
    verifier.calc_county_column_indexes()
    error_count += verifier.verify_counties()
    error_count += verifier.verify_offices()
    error_count += verifier.verify_districts()
    error_count += verifier.verify_votes()
    error_count += verifier.verify_candidate_party_relationship()
    error_count += verifier.verify_candidate_office_relationship()
    error_count += verifier.verify_candidate_district_relationship()

    print 'There were ' + str(error_count) + ' invalid values in the County File.'

    return

def process_muni_file(args, in_file):

    error_count = 0

    verifier = VerifyMuni(in_file, args.verbose, args.case)   
    verifier.calc_muni_column_indexes()
    error_count += verifier.verify_counties()
    error_count += verifier.verify_offices()
    error_count += verifier.verify_districts()
    error_count += verifier.verify_votes()
    error_count += verifier.verify_candidate_party_relationship()
    error_count += verifier.verify_candidate_office_relationship()
    error_count += verifier.verify_candidate_district_relationship()

    print 'There were ' + str(error_count) + ' invalid values in the Municipality File.'

    return

def compare_county_and_muni_totals(args, county_file, muni_file):

    error_count = 0

    cv = VerifyCounty(county_file, args.verbose, args.case)
    cv.calc_county_column_indexes()
    mv = VerifyMuni(muni_file, args.verbose, args.case)
    mv.calc_muni_column_indexes()

    county_votes = cv.get_all_candidates_and_votes_by_county('Morris')
    for cand in county_votes:
        print cand + ' got ' + str(county_votes[cand]) + ' in Morris County'
        #muni_total = mv.get_candidates_votes_by_county('Morris', cand)
        #print cand + ' C:' + str(county_votes[cand]) + '    M:' + str(muni_total)

    return

if __name__ == '__main__':
    main()
