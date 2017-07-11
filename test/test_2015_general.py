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

    CONST_COUNTY_FILE = '../2015/20151103__nj__general__county.csv'
    CONST_MUNI_FILE = '../2015/20151103__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2015 General Election county and muni data')
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
    #1
    error_count += spot_check_value(args, cv, 'Bob Andrzejczak', 'Atlantic', 692)
    error_count += spot_check_value(args, cv, 'Sam Fiocchi', 'Cape May', 9495)
    error_count += spot_check_value(args, cv, 'Jim Sauro', 'Cumberland', 6884)
    #2
    error_count += spot_check_value(args, cv, 'Chris Brown', 'Atlantic', 18959)
    #3
    error_count += spot_check_value(args, cv, 'Adam Taliaferro', 'Cumberland', 1547)
    error_count += spot_check_value(args, cv, 'John Kalnas', 'Gloucester', 739)
    error_count += spot_check_value(args, cv, 'Leroy P. Pierce III', 'Salem', 6314)
    #4
    error_count += spot_check_value(args, cv, 'Paul D. Moriarty', 'Camden', 9846)
    error_count += spot_check_value(args, cv, 'Jack Nicholson', 'Gloucester', 6090)
    #5
    error_count += spot_check_value(args, cv, 'Arthur Barclay', 'Camden', 9551)
    error_count += spot_check_value(args, cv, 'Kevin P. Ehret', 'Gloucester', 4482)
    #6
    error_count += spot_check_value(args, cv, 'Holly Tate', 'Burlington', 601)
    error_count += spot_check_value(args, cv, 'Amanda Davis', 'Camden', 936)
    #7
    error_count += spot_check_value(args, cv, 'Rob Prisco', 'Burlington', 13949)
    #8
    error_count += spot_check_value(args, cv, 'Maria Rodriguez-Gregg', 'Atlantic', 1989)
    error_count += spot_check_value(args, cv, 'Joe Howarth', 'Burlington', 13886)
    error_count += spot_check_value(args, cv, 'Maria Rodriguez-Gregg', 'Camden', 2385)
    #9
    error_count += spot_check_value(args, cv, 'Brian E. Rumpf', 'Atlantic', 2983)
    error_count += spot_check_value(args, cv, 'Dianne C. Gove', 'Burlington', 1018)
    error_count += spot_check_value(args, cv, 'Fran Zimmer', 'Ocean', 9894)
    #10
    error_count += spot_check_value(args, cv, 'Kimberley S. Casten', 'Ocean', 12302)
    #11
    error_count += spot_check_value(args, cv, 'Mary Pat Angelini', 'Monmouth', 14653)
    #12
    error_count += spot_check_value(args, cv, 'Robert D. Clifton', 'Burlington', 1167)
    error_count += spot_check_value(args, cv, 'David W. Merwin', 'Middlesex', 4284)
    error_count += spot_check_value(args, cv, 'Stephen N. Zielinski Sr.', 'Monmouth', 318)
    error_count += spot_check_value(args, cv, 'Robert P. Kurzydlowski', 'Ocean', 2108)
    #13
    error_count += spot_check_value(args, cv, 'Amy Handlin', 'Monmouth', 19829)
    #14
    error_count += spot_check_value(args, cv, 'Wayne P. DeAngelo', 'Mercer', 14226)
    error_count += spot_check_value(args, cv, 'Joann Cousin', 'Middlesex', 355)
    #15
    error_count += spot_check_value(args, cv, 'Reed Gusciora', 'Hunterdon', 1254)
    error_count += spot_check_value(args, cv, 'Anthony L. Giordano', 'Mercer', 6373)
    #16
    error_count += spot_check_value(args, cv, 'Jack M. Ciattarelli', 'Hunterdon', 5869)
    error_count += spot_check_value(args, cv, 'Donna M. Simon', 'Mercer', 944)
    error_count += spot_check_value(args, cv, 'Andrew Zwicker', 'Middlesex', 3142)
    error_count += spot_check_value(args, cv, 'Maureen Vella', 'Somerset', 6306)
    #17
    error_count += spot_check_value(args, cv, 'Joseph V. Egan', 'Middlesex', 8179)
    error_count += spot_check_value(args, cv, 'Molly O\'Brien', 'Somerset', 380)
    #18
    error_count += spot_check_value(args, cv, 'Patrick J. Diegnan Jr.', 'Middlesex', 16256)
    #19
    error_count += spot_check_value(args, cv, 'Thomas E. Maras', 'Middlesex', 6597)
    #20
    error_count += spot_check_value(args, cv, 'Roger Stryeski', 'Union', 3398)
    #21
    error_count += spot_check_value(args, cv, 'Jon Bramnick', 'Morris', 1419)
    error_count += spot_check_value(args, cv, 'Nancy Munoz', 'Somerset', 3992)
    error_count += spot_check_value(args, cv, 'Jill Anne Lazare', 'Union', 11158)
    #22
    error_count += spot_check_value(args, cv, 'Gerald "Jerry" Green', 'Middlesex', 1450)
    error_count += spot_check_value(args, cv, 'William "Bo" Vastine', 'Somerset', 900)
    error_count += spot_check_value(args, cv, 'William H. Michelson', 'Union', 5390)
    #23
    error_count += spot_check_value(args, cv, 'Erik Peterson', 'Hunterdon', 5879)
    error_count += spot_check_value(args, cv, 'John DiMaio', 'Somerset', 7007)
    error_count += spot_check_value(args, cv, 'MaryBeth Maciag', 'Warren', 2726)
    #24
    error_count += spot_check_value(args, cv, 'F. Parker Space', 'Morris', 1129)
    error_count += spot_check_value(args, cv, 'Michael F. Grace', 'Sussex', 5432)
    error_count += spot_check_value(args, cv, 'Kenneth Collins', 'Warren', 323)
    #25
    error_count += spot_check_value(args, cv, 'Richard J. Corcoran III', 'Morris', 9650)
    error_count += spot_check_value(args, cv, 'Thomas Moran', 'Somerset', 558)
    #26
    error_count += spot_check_value(args, cv, 'Jay Webber', 'Essex', 1766)
    error_count += spot_check_value(args, cv, 'BettyLou DeCroce', 'Morris', 8898)
    error_count += spot_check_value(args, cv, 'Wayne B. Marek', 'Passaic', 1620)
    #27
    error_count += spot_check_value(args, cv, 'John F. McKeon', 'Essex', 13912)
    error_count += spot_check_value(args, cv, 'Tayfun Selen', 'Morris', 7383)
    #28
    error_count += spot_check_value(args, cv, 'Cleopatra G. Tucker', 'Essex', 9186)
    #29
    error_count += spot_check_value(args, cv, 'Pablo Olivera', 'Essex', 498)
    #30
    error_count += spot_check_value(args, cv, 'David P. Rible', 'Monmouth', 10738)
    error_count += spot_check_value(args, cv, 'Hank Schroeder', 'Ocean', 177)
    #31
    error_count += spot_check_value(args, cv, 'Herminio Mendoza', 'Hudson', 2603)
    #32
    error_count += spot_check_value(args, cv, 'Vincent Prieto', 'Bergen', 1452)
    error_count += spot_check_value(args, cv, 'LisaMarie Tusa', 'Hudson', 1873)
    #33
    error_count += spot_check_value(args, cv, 'Raj Mukherji', 'Hudson', 11978)
    #34
    error_count += spot_check_value(args, cv, 'Sheila Y. Oliver', 'Essex', 9291)
    error_count += spot_check_value(args, cv, 'John M. Traier', 'Passaic', 3454)
    #35
    error_count += spot_check_value(args, cv, 'Shavonda E. Sumter', 'Bergen', 2352)
    error_count += spot_check_value(args, cv, 'David Jimenez', 'Passaic', 2719)
    #36
    error_count += spot_check_value(args, cv, 'Gary Schaer', 'Bergen', 11728)
    error_count += spot_check_value(args, cv, 'Jeff Boss', 'Passaic', 60)
    #37
    error_count += spot_check_value(args, cv, 'Valerie Vainieri Huttle', 'Bergen', 18930)
    #38
    error_count += spot_check_value(args, cv, 'Tim Eustace', 'Bergen', 18410)
    error_count += spot_check_value(args, cv, 'Mark Dipisa', 'Passaic', 1502)
    #39
    error_count += spot_check_value(args, cv, 'Robert Auth', 'Bergen', 17177)
    error_count += spot_check_value(args, cv, 'John DeRienzo', 'Passaic', 1917)
    #40
    error_count += spot_check_value(args, cv, 'David C. Russo', 'Bergen', 7081)
    error_count += spot_check_value(args, cv, 'Scott T. Rumana', 'Essex', 778)
    error_count += spot_check_value(args, cv, 'Christine Ordway', 'Morris', 1060)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
