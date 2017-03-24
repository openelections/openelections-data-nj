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

    CONST_COUNTY_FILE = '../2013/20131105__nj__general__county.csv'
    CONST_MUNI_FILE = '../2013/20131105__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2013 General Election county and muni data')
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
    error_count += spot_check_value(args, cv, 'Jeff Van Drew', 'Atlantic', 977)
    error_count += spot_check_value(args, cv, 'Frank X. Balles', 'Atlantic', 24006)
    error_count += spot_check_value(args, cv, 'John J. Burzichelli', 'Gloucester', 18100)
    error_count += spot_check_value(args, cv, 'Gabriela M. Mosquera', 'Camden', 15687)
    error_count += spot_check_value(args, cv, 'Gilbert L. "Whip" Wilson', 'Gloucester', 9251)
    error_count += spot_check_value(args, cv, 'Chris Leone-Zwillinger', 'Burlington', 1607)
    error_count += spot_check_value(args, cv, 'Jeff Banasz', 'Burlington', 27233)
    error_count += spot_check_value(args, cv, 'Dawn Marie Addiego', 'Camden', 3667)
    error_count += spot_check_value(args, cv, 'Anthony Mazzella', 'Ocean', 14856)
    error_count += spot_check_value(args, cv, 'Dave Wolfe', 'Ocean', 44627)
    error_count += spot_check_value(args, cv, 'Marie E. Amato-Juckiewicz', 'Monmouth', 599)
    error_count += spot_check_value(args, cv, 'Robert D. Clifton', 'Burlington', 1973)
    error_count += spot_check_value(args, cv, 'Declan O\'Scanlon', 'Monmouth', 37577)
    error_count += spot_check_value(args, cv, 'Steve Cook', 'Middlesex', 10893)
    error_count += spot_check_value(args, cv, 'Anthony Giordano', 'Hunterdon', 2041)
    error_count += spot_check_value(args, cv, 'Christopher "Kip" Bateman', 'Somerset', 17630)
    error_count += spot_check_value(args, cv, 'Carlo DiLalla', 'Middlesex', 8237)
    error_count += spot_check_value(args, cv, 'Sheila Angalet', 'Middlesex', 1068)
    error_count += spot_check_value(args, cv, 'Joseph F. Vitale', 'Middlesex', 24126)
    error_count += spot_check_value(args, cv, 'Annette Quijano', 'Union', 18839)
    error_count += spot_check_value(args, cv, 'Norman W. Albert', 'Union', 15015)
    error_count += spot_check_value(args, cv, 'John Campbell', 'Middlesex', 2490)
    error_count += spot_check_value(args, cv, 'Michael J. Doherty', 'Warren', 10367)
    error_count += spot_check_value(args, cv, 'Richard D. Tomko', 'Sussex', 11653)
    error_count += spot_check_value(args, cv, 'Rebecca Feldman', 'Morris', 8731)
    error_count += spot_check_value(args, cv, 'Joseph Raich', 'Essex', 3532)
    error_count += spot_check_value(args, cv, 'Angelo Tedesco', 'Morris', 12767)
    error_count += spot_check_value(args, cv, 'Ronald L. Rice', 'Essex', 27265)
    error_count += spot_check_value(args, cv, 'Pablo Olivera', 'Essex', 808)
    error_count += spot_check_value(args, cv, 'David P. Rible', 'Monmouth', 23070)
    error_count += spot_check_value(args, cv, 'Sandra Bolden Cunningham', 'Hudson', 18822)
    error_count += spot_check_value(args, cv, 'Maria Malavasi-Quartello', 'Bergen', 842)
    error_count += spot_check_value(args, cv, 'Armando Hernandez', 'Hudson', 7737)
    error_count += spot_check_value(args, cv, 'Nia H. Gill', 'Passaic', 7101)
    error_count += spot_check_value(args, cv, 'Shavonda E. Sumter', 'Passaic', 17290)
    error_count += spot_check_value(args, cv, 'Marlene Caride', 'Bergen', 16405)
    error_count += spot_check_value(args, cv, 'Valerie Vainieri Huttle', 'Bergen', 26581)
    error_count += spot_check_value(args, cv, 'Joseph J. Scarpa', 'Bergen', 23259)
    error_count += spot_check_value(args, cv, 'Anthony N. Iannarelli Jr.', 'Passaic', 3194)
    error_count += spot_check_value(args, cv, 'Kevin J. O\'Toole', 'Bergen', 14674)
    error_count += spot_check_value(args, cv, 'Chris Christie - Kimberly M. Guadagno', 'Atlantic', 43975)
    error_count += spot_check_value(args, cv, 'Barbara Buono - Milly Silva', 'Bergen', 87376)
    error_count += spot_check_value(args, cv, 'William Araujo - Maria Salamanca', 'Burlington', 186)
    error_count += spot_check_value(args, cv, 'Jeff Boss - Robert B. Thorne', 'Camden', 130)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan - Brenda Bell', 'Cape May', 178)
    error_count += spot_check_value(args, cv, 'Diane W. Sare - Bruce Todd', 'Cumberland', 147)
    error_count += spot_check_value(args, cv, 'Hank Schroeder - Patricia Moschella', 'Essex', 118)
    error_count += spot_check_value(args, cv, 'Steven Welzer - Patrice Alessandrini', 'Gloucester', 262)
    error_count += spot_check_value(args, cv, 'Chris Christie - Kimberly M. Guadagno', 'Hudson', 42567)
    error_count += spot_check_value(args, cv, 'Barbara Buono - Milly Silva', 'Hunterdon', 10425)
    error_count += spot_check_value(args, cv, 'William Araujo - Maria Salamanca', 'Mercer', 101)
    error_count += spot_check_value(args, cv, 'Jeff Boss - Robert B. Thorne', 'Middlesex', 141)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan - Brenda Bell', 'Monmouth', 1032)
    error_count += spot_check_value(args, cv, 'Diane W. Sare - Bruce Todd', 'Morris', 209)
    error_count += spot_check_value(args, cv, 'Hank Schroeder - Patricia Moschella', 'Ocean', 191)
    error_count += spot_check_value(args, cv, 'Steven Welzer - Patrice Alessandrini', 'Passaic', 213)
    error_count += spot_check_value(args, cv, 'Chris Christie - Kimberly M. Guadagno', 'Salem', 12748)
    error_count += spot_check_value(args, cv, 'Barbara Buono - Milly Silva', 'Somerset', 26913)
    error_count += spot_check_value(args, cv, 'William Araujo - Maria Salamanca', 'Sussex', 130)
    error_count += spot_check_value(args, cv, 'Jeff Boss - Robert B. Thorne', 'Union', 95)
    error_count += spot_check_value(args, cv, 'Kenneth R. Kaplan - Brenda Bell', 'Warren', 238)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
