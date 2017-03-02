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
    spot_check_totals(args)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2016 county and muni data')
    arg_parser.add_argument('--verbose', '-v', dest='verbose',  help='report information verbosely', action='store_true')
    arg_parser.add_argument('--case', '-c', dest='case',  help='case sensitive text compare', action='store_true')
    return arg_parser.parse_args()

def process_county_file(args, in_file):

    error_count = 0

    verifier = VerifyCounty(in_file, args.verbose, args.case)   
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
    mv = VerifyMuni(muni_file, args.verbose, args.case)

    for county_name in CONST_COUNTIES:
        print ' ... processing ' + county_name + ' County'
        county_votes = cv.get_all_candidates_and_votes_by_county(county_name)
        for cand in county_votes:
            muni_total = mv.get_candidates_votes_by_county(county_name, cand)
            if muni_total != county_votes[cand]:
                error_count += 1
                if args.verbose:
                    print "Total votes are different in County (" + \
                          str(county_votes[cand]) + ") and Municipal (" + \
                          str(muni_total) + ") for " + cand + " in " + \
                          county_name + " County."

    print "There are " + str(error_count) + " vote totals that are not reconciled."

def spot_check_totals(args)

    error_count = 0



if __name__ == '__main__':
    main()
