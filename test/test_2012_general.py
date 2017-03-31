#!/usr/bin/python
#
# MIT License
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import sys
import argparse
import csv
from collections import defaultdict
from nj_common import *

def main():

    CONST_COUNTY_FILE = '../2012/20121106__nj__general.csv'
    CONST_MUNI_FILE = '../2012/20121106__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2012 General Election county and muni data')
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
    error_count += spot_check_value(args, cv, 'Robert Menendez', 'Atlantic', 61464)
    error_count += spot_check_value(args, cv, 'Joe Kyrillos', 'Bergen', 144709)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan', 'Burlington', 594)
    error_count += spot_check_value(args, cv, 'Ken Wolski', 'Camden', 1228)
    error_count += spot_check_value(args, cv, 'Gwen Diakos', 'Cape May', 116)
    error_count += spot_check_value(args, cv, 'J. David Dranikoff', 'Cumberland', 246)
    error_count += spot_check_value(args, cv, "Inder 'Andy' Soni", 'Cumberland', 97)
    error_count += spot_check_value(args, cv, "Robert 'Turk' Turkavage", 'Essex', 215)
    error_count += spot_check_value(args, cv, 'Gregory Pason', 'Gloucester', 42)
    error_count += spot_check_value(args, cv, 'Eugene Martin Lavergne', 'Hudson', 197)
    error_count += spot_check_value(args, cv, 'Daryl Mikell Brooks', 'Hunterdon', 45)
    error_count += spot_check_value(args, cv, 'Robert Menendez', 'Mercer', 97964)
    error_count += spot_check_value(args, cv, 'Joe Kyrillos', 'Middlesex', 97730)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan', 'Monmouth', 1291)
    error_count += spot_check_value(args, cv, 'Ken Wolski', 'Morris', 513)
    error_count += spot_check_value(args, cv, 'Gwen Diakos', 'Ocean', 689)
    error_count += spot_check_value(args, cv, 'J. David Dranikoff', 'Passaic', 120)
    error_count += spot_check_value(args, cv, "Inder 'Andy' Soni", 'Somerset', 173)
    error_count += spot_check_value(args, cv, "Robert 'Turk' Turkavage", 'Salem', 45)
    error_count += spot_check_value(args, cv, 'Gregory Pason', 'Sussex', 77)
    error_count += spot_check_value(args, cv, 'Eugene Martin Lavergne', 'Union', 29)
    error_count += spot_check_value(args, cv, 'Daryl Mikell Brooks', 'Warren', 41)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan', 'Warren', 229)
    error_count += spot_check_value(args, cv, 'Ken Wolski', 'Union', 490)
    error_count += spot_check_value(args, cv, 'Gwen Diakos', 'Sussex', 1050)
    error_count += spot_check_value(args, cv, 'J. David Dranikoff', 'Somerset', 188)
    error_count += spot_check_value(args, cv, "Inder 'Andy' Soni", 'Salem', 70)
    error_count += spot_check_value(args, cv, "Robert 'Turk' Turkavage", 'Passaic', 115)
    error_count += spot_check_value(args, cv, 'Gregory Pason', 'Ocean', 120)
    error_count += spot_check_value(args, cv, 'Eugene Martin Lavergne', 'Morris', 34)
    error_count += spot_check_value(args, cv, 'Daryl Mikell Brooks', 'Monmouth', 143)
    error_count += spot_check_value(args, cv, 'Robert Menendez', 'Middlesex', 178686)
    error_count += spot_check_value(args, cv, 'Joe Kyrillos', 'Mercer', 43793)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan', 'Hunterdon', 660)
    error_count += spot_check_value(args, cv, 'Ken Wolski', 'Hudson', 1395)
    error_count += spot_check_value(args, cv, 'Gwen Diakos', 'Gloucester', 152)
    error_count += spot_check_value(args, cv, 'J. David Dranikoff', 'Essex', 225)
    error_count += spot_check_value(args, cv, "Inder 'Andy' Soni", 'Cape May', 98)
    error_count += spot_check_value(args, cv, "Robert 'Turk' Turkavage", 'Camden', 178)
    error_count += spot_check_value(args, cv, 'Gregory Pason', 'Burlington', 70)
    error_count += spot_check_value(args, cv, 'Eugene Martin Lavergne', 'Bergen', 85)
    error_count += spot_check_value(args, cv, 'Daryl Mikell Brooks', 'Atlantic', 89)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
