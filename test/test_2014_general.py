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

    CONST_COUNTY_FILE = '../2014/20141104__nj__general__county.csv'
    CONST_MUNI_FILE = '../2014/20141104__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2014 Special Election county and muni data')
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
    error_count += spot_check_value(args, cv, 'Donald W. Norcross', 'Burlington', 3148)
    error_count += spot_check_value(args, cv, 'Garry W. Cobb', 'Camden', 39668)
    error_count += spot_check_value(args, cv, 'Scot John Tomaszewski', 'Gloucester', 237)
    error_count += spot_check_value(args, cv, 'Gary Stein', 'Atlantic', 187)
    error_count += spot_check_value(args, cv, 'Aimee Belgard', 'Burlington', 55305)
    error_count += spot_check_value(args, cv, 'Tom MacArthur', 'Ocean', 45518)
    error_count += spot_check_value(args, cv, 'Scott Neuman', 'Mercer', 342)
    error_count += spot_check_value(args, cv, 'Christopher H. Smith', 'Monmouth', 66308)
    error_count += spot_check_value(args, cv, 'Ruben M. Scolavino', 'Ocean', 11816)
    error_count += spot_check_value(args, cv, 'Scott Garrett', 'Bergen', 71318)
    error_count += spot_check_value(args, cv, 'Roy Cho', 'Passaic', 3233)
    error_count += spot_check_value(args, cv, 'Mark D. Quick', 'Sussex', 642)
    error_count += spot_check_value(args, cv, 'Frank Pallone Jr.', 'Middlesex', 48471)
    error_count += spot_check_value(args, cv, 'Anthony E. Wilkinson', 'Monmouth', 21372)
    error_count += spot_check_value(args, cv, 'Leonard Lance', 'Essex', 2396)
    error_count += spot_check_value(args, cv, 'Janice Kovach', 'Hunterdon', 12707) 
    error_count += spot_check_value(args, cv, 'James Gawron', 'Morris', 422)
    error_count += spot_check_value(args, cv, 'Leonard Lance', 'Somerset', 33693)
    error_count += spot_check_value(args, cv, 'Janice Kovach', 'Union', 19416)
    error_count += spot_check_value(args, cv, 'James Gawron', 'Warren', 340)
    error_count += spot_check_value(args, cv, 'Albio Sires', 'Bergen', 1189)
    error_count += spot_check_value(args, cv, 'Jude Anthony Tiscornia', 'Essex', 2358)
    error_count += spot_check_value(args, cv, 'Herbert H. Shaw', 'Hudson', 1023)
    error_count += spot_check_value(args, cv, 'Pablo Olivera', 'Union', 185)
    error_count += spot_check_value(args, cv, 'Bill Pascrell Jr.', 'Bergen', 44410)
    error_count += spot_check_value(args, cv, 'Dierdre G. Paul', 'Hudson', 1791)
    error_count += spot_check_value(args, cv, 'Nestor Montilla', 'Passaic', 754)
    error_count += spot_check_value(args, cv, 'Donald M. Payne Jr.', 'Essex', 59989)
    error_count += spot_check_value(args, cv, 'Yolanda Dentley', 'Hudson', 2748)
    error_count += spot_check_value(args, cv, 'Gwendolyn A. Franklin', 'Union', 261)
    error_count += spot_check_value(args, cv, 'Rodney P. Frelinghuysen', 'Essex', 22924)
    error_count += spot_check_value(args, cv, 'Mark Dunec', 'Morris', 29778)
    error_count += spot_check_value(args, cv, 'Rodney P. Frelinghuysen', 'Passaic', 19525)
    error_count += spot_check_value(args, cv, 'Mark Dunec', 'Sussex', 3375)
    error_count += spot_check_value(args, cv, 'Bonnie Watson Coleman', 'Mercer', 38168)
    error_count += spot_check_value(args, cv, 'Alieta Eck', 'Middlesex', 26917)
    error_count += spot_check_value(args, cv, 'Don DeZarn', 'Somerset', 200)
    error_count += spot_check_value(args, cv, 'Steven Welzer', 'Union', 55)
    error_count += spot_check_value(args, cv, 'Cory Booker', 'Atlantic', 32566)
    error_count += spot_check_value(args, cv, 'Jeff Bell', 'Bergen', 89597)
    error_count += spot_check_value(args, cv, 'Joseph Baratelli', 'Burlington', 907)
    error_count += spot_check_value(args, cv, 'Eugene Martin LaVergne', 'Camden', 211)
    error_count += spot_check_value(args, cv, 'Hank Schroeder', 'Cape May', 62)
    error_count += spot_check_value(args, cv, 'Jeff Boss', 'Cumberland', 128)
    error_count += spot_check_value(args, cv, 'Antonio N. Sabas', 'Essex', 354)
    error_count += spot_check_value(args, cv, 'Cory Booker', 'Gloucester', 37131)
    error_count += spot_check_value(args, cv, 'Jeff Bell', 'Hudson', 16707)
    error_count += spot_check_value(args, cv, 'Joseph Baratelli', 'Hunterdon', 472)
    error_count += spot_check_value(args, cv, 'Eugene Martin LaVergne', 'Mercer', 222)
    error_count += spot_check_value(args, cv, 'Hank Schroeder', 'Middlesex', 629)
    error_count += spot_check_value(args, cv, 'Jeff Boss', 'Monmouth', 324)
    error_count += spot_check_value(args, cv, 'Antonio N. Sabas', 'Morris', 161)
    error_count += spot_check_value(args, cv, 'Cory Booker', 'Ocean', 55631)
    error_count += spot_check_value(args, cv, 'Jeff Bell', 'Passaic', 32612)
    error_count += spot_check_value(args, cv, 'Joseph Baratelli', 'Salem', 260)
    error_count += spot_check_value(args, cv, 'Eugene Martin LaVergne', 'Somerset', 58)
    error_count += spot_check_value(args, cv, 'Hank Schroeder', 'Sussex', 182)
    error_count += spot_check_value(args, cv, 'Jeff Boss', 'Union', 139)
    error_count += spot_check_value(args, cv, 'Antonio N. Sabas', 'Warren', 60)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
