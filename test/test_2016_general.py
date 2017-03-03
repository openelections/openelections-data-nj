#!/usr/bin/python

import sys
import argparse
import csv
from collections import defaultdict
from nj_common import *

def main():

    CONST_COUNTY_FILE = '../2016/20161108__nj__general.csv'
    CONST_MUNI_FILE = '../2016/20161108__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

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

def spot_check_value(args, county_verifier, candidate_name, county_name, total_votes):

    error_count = 1

    vote_calc =  county_verifier.get_candidates_votes_by_county(county_name, candidate_name)
    if vote_calc == total_votes:
        error_count = 0
    else:
        if args.verbose:
            print candidate_name + ' / ' + county_name + ' value is ' + str(vote_calc) + \
                  '  ---  Expected value: ' + str(total_votes)

    return error_count

def spot_check_totals(args, county_file):

    error_count = 0

    cv = VerifyCounty(county_file, args.verbose, args.case)

    ### Spot check at least one value from each input file
    error_count += spot_check_value(args, cv, 'Jill Stein', 'Atlantic', 999)
    error_count += spot_check_value(args, cv, 'Donald J. Trump', 'Bergen', 175529)
    error_count += spot_check_value(args, cv, 'Gary Johnson', 'Burlington', 4946)
    error_count += spot_check_value(args, cv, 'Hillary Rodham Clinton', 'Camden', 146717)
    error_count += spot_check_value(args, cv, 'Darrell Castle', 'Cape May', 167)
    error_count += spot_check_value(args, cv, 'Alyson Kennedy', 'Cumberland', 31)
    error_count += spot_check_value(args, cv, 'Rocky Roque De la Fuente', 'Essex', 304)
    error_count += spot_check_value(args, cv, 'Monica Moorehead', 'Gloucester', 224)
    error_count += spot_check_value(args, cv, 'Gloria La Riva', 'Hudson', 347)
    error_count += spot_check_value(args, cv, 'Hillary Rodham Clinton', 'Hunterdon', 28898)
    error_count += spot_check_value(args, cv, 'Donald J. Trump', 'Mercer', 46193)
    error_count += spot_check_value(args, cv, 'Gary Johnson', 'Middlesex', 5446)
    error_count += spot_check_value(args, cv, 'Jill Stein', 'Monmouth', 3189)
    error_count += spot_check_value(args, cv, 'Darrell Castle', 'Morris', 334)
    error_count += spot_check_value(args, cv, 'Alyson Kennedy', 'Ocean', 92)
    error_count += spot_check_value(args, cv, 'Rocky Roque De la Fuente', 'Passaic', 83)
    error_count += spot_check_value(args, cv, 'Monica Moorehead', 'Salem', 16)
    error_count += spot_check_value(args, cv, 'Gloria La Riva', 'Somerset', 35)
    error_count += spot_check_value(args, cv, 'Hillary Rodham Clinton', 'Sussex', 24212)
    error_count += spot_check_value(args, cv, 'Donald J. Trump', 'Union', 68114)
    error_count += spot_check_value(args, cv, 'Gary Johnson', 'Warren', 1261)
    error_count += spot_check_value(args, cv, 'Donald W. Norcross', 'Burlington', 6000)
    error_count += spot_check_value(args, cv, 'David H. Pinckney', 'Essex', 9463)
    error_count += spot_check_value(args, cv, 'Jeff Hetrick', 'Morris', 1428)
    error_count += spot_check_value(args, cv, 'R. Edward Forchion', 'Union', 261)
    error_count += spot_check_value(args, cv, 'John Ordille', 'Burlington', 14)
    error_count += spot_check_value(args, cv, 'Tom MacArthur', 'Ocean', 95147)
    error_count += spot_check_value(args, cv, 'Lorna Phillipson', 'Monmouth', 71105)
    error_count += spot_check_value(args, cv, 'Claudio Belusic', 'Passaic', 387)
    error_count += spot_check_value(args, cv, 'Judith Shamy', 'Middlesex', 1065)
    error_count += spot_check_value(args, cv, 'Dan O\'Neill', 'Hunterdon', 2096)
    error_count += spot_check_value(args, cv, 'Albio Sires', 'Hudson', 89305)
    error_count += spot_check_value(args, cv, 'Hector L. Castillo', 'Bergen', 43308)
    error_count += spot_check_value(args, cv, 'Patrick J. Diegnan Jr.', 'Middlesex', 50537)
    error_count += spot_check_value(args, cv, 'Camille Ferraro Clark', 'Middlesex', 31827)
    error_count += spot_check_value(args, cv, 'Blonnie R. Watson', 'Essex', 40208)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
