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

    CONST_COUNTY_FILE = '../2011/20111108__nj__general.csv'
    CONST_MUNI_FILE = '../2011/20111108__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2011 General Election county and muni data')
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
    # District 1
    error_count += spot_check_value(args, cv, 'Jeff Van Drew', 'Atlantic', 780)
    error_count += spot_check_value(args, cv, 'Matthew Milam', 'Cape May', 11029)
    error_count += spot_check_value(args, cv, 'Suzanne M. Walters', 'Cumberland', 7508)
    # District 2
    error_count += spot_check_value(args, cv, 'Vince Polistina', 'Atlantic', 20997)
    error_count += spot_check_value(args, cv, 'Damon Tyner', 'Atlantic', 19919)
    # District 3
    error_count += spot_check_value(args, cv, 'Stephen M. Sweeney', 'Cumberland', 2472)
    error_count += spot_check_value(args, cv, 'Celeste M. Riley', 'Gloucester', 13541)
    error_count += spot_check_value(args, cv, 'Domenick DiCicco', 'Salem', 6905)
    # District 4
    error_count += spot_check_value(args, cv, 'Giancarlo D\'Orazio', 'Camden', 6773)
    error_count += spot_check_value(args, cv, 'Gabriela Mosquera', 'Gloucester', 9292)
    # District 5
    error_count += spot_check_value(args, cv, 'Donald W. Norcross', 'Camden', 10884)
    error_count += spot_check_value(args, cv, 'Terrell A. Ratliff', 'Gloucester', 6837)
    # District 6
    error_count += spot_check_value(args, cv, 'Phil Mitsch', 'Burlington', 863)
    error_count += spot_check_value(args, cv, 'Pamela R. Lampitt', 'Camden', 22255)
    # District 7
    error_count += spot_check_value(args, cv, 'Gail Cook', 'Burlington', 20370)
    error_count += spot_check_value(args, cv, 'Herb Conaway', 'Burlington', 23908)
    # District 8
    error_count += spot_check_value(args, cv, 'Dawn Marie Addiego', 'Atlantic', 2166)
    error_count += spot_check_value(args, cv, 'Anita Lovely', 'Burlington', 9852)
    error_count += spot_check_value(args, cv, 'Robert Edward Forchion Jr.', 'Camden', 189)
    # District 9
    error_count += spot_check_value(args, cv, 'Christopher J. Connors', 'Atlantic', 4088)
    error_count += spot_check_value(args, cv, 'Brian E. Rumpf', 'Burlington', 1221)
    error_count += spot_check_value(args, cv, 'DiAnne C. Gove', 'Ocean', 24867)
    # District 10
    error_count += spot_check_value(args, cv, 'Charles P. Tivenan', 'Ocean', 16105)
    error_count += spot_check_value(args, cv, 'Gregory P. McGuckin', 'Ocean', 26831)
    # District 11
    error_count += spot_check_value(args, cv, 'Jennifer Beck', 'Monmouth', 20226)
    error_count += spot_check_value(args, cv, 'Mary Pat Angelini', 'Monmouth', 18479)
    # District 12
    error_count += spot_check_value(args, cv, 'Robert "Bob" Brown', 'Burlington', 665)
    error_count += spot_check_value(args, cv, 'Robert D. Clifton', 'Middlesex', 5125)
    error_count += spot_check_value(args, cv, 'Catherine Tinney Rome', 'Monmouth', 4087)
    error_count += spot_check_value(args, cv, 'Samuel D. Thompson', 'Ocean', 9499)
    # District 13
    error_count += spot_check_value(args, cv, 'Stephen J. Boracchia', 'Monmouth', 556)
    error_count += spot_check_value(args, cv, 'Frank C. Cottone', 'Monmouth', 834)
    # District 14
    error_count += spot_check_value(args, cv, 'Linda R. Greenstein', 'Mercer', 15750)
    error_count += spot_check_value(args, cv, 'Daniel R. Benson', 'Middlesex', 9704)
    # District 15
    error_count += spot_check_value(args, cv, 'Shirley K. Turner', 'Hunterdon', 1301)
    error_count += spot_check_value(args, cv, 'Peter M. Yull', 'Mercer', 9597)
    # District 16
    error_count += spot_check_value(args, cv, 'Christopher "Kip" Bateman', 'Hunterdon', 5920)
    error_count += spot_check_value(args, cv, 'Marie Corfield', 'Mercer', 4711)
    error_count += spot_check_value(args, cv, 'Joe Camarota', 'Middlesex', 3313)
    error_count += spot_check_value(args, cv, 'Maureen Vella', 'Somerset', 6600)
    # District 17
    error_count += spot_check_value(args, cv, 'Jordan Rickards', 'Middlesex', 4991)
    error_count += spot_check_value(args, cv, 'Upendra Chivukula', 'Somerset', 5824)
    # District 18
    error_count += spot_check_value(args, cv, 'Barbara Buono', 'Middlesex', 19631)
    error_count += spot_check_value(args, cv, 'Peter J. Barnes III', 'Middlesex', 18166)
    # District 19
    error_count += spot_check_value(args, cv, 'Paul Lund, Jr.', 'Middlesex', 9232)
    error_count += spot_check_value(args, cv, 'Craig J. Coughlin', 'Middlesex', 17492)
    # District 20
    error_count += spot_check_value(args, cv, 'Raymond J. Lesniak', 'Union', 12510)
    error_count += spot_check_value(args, cv, 'Annette Quijano', 'Union', 12116)
    # District 21
    error_count += spot_check_value(args, cv, 'Thomas H. Kean, Jr.', 'Morris', 2521)
    error_count += spot_check_value(args, cv, 'Nancy F. Munoz', 'Somerset', 5667)
    error_count += spot_check_value(args, cv, 'Darren Young', 'Union', 907)
    # District 22
    error_count += spot_check_value(args, cv, 'Michael W. Class', 'Middlesex', 1861)
    error_count += spot_check_value(args, cv, 'Linda Stender', 'Somerset', 1417)
    error_count += spot_check_value(args, cv, 'Jeffrey D. First', 'Union', 6851)
    # District 23
    error_count += spot_check_value(args, cv, 'John Graf, Jr.', 'Hunterdon', 3801)
    error_count += spot_check_value(args, cv, 'Erik Peterson', 'Somerset', 8033)
    error_count += spot_check_value(args, cv, 'Karen Carroll', 'Warren', 3717)
    # District 24
    error_count += spot_check_value(args, cv, 'Steven V. Oroho', 'Morris', 2281)
    error_count += spot_check_value(args, cv, 'Alison Littell McHose', 'Sussex', 13798)
    error_count += spot_check_value(args, cv, 'Leslie Huhn', 'Warren', 1590)
    # District 25
    error_count += spot_check_value(args, cv, 'Anthony "Tony" Bucco', 'Somerset', 1201)
    error_count += spot_check_value(args, cv, 'George Stafford', 'Morris', 11876)
    # District 26
    error_count += spot_check_value(args, cv, 'Wasim Khan', 'Essex', 2006)
    error_count += spot_check_value(args, cv, 'Jay Webber', 'Morris', 12905)
    error_count += spot_check_value(args, cv, 'Michael Spector', 'Passaic', 195)
    # District 27
    error_count += spot_check_value(args, cv, 'Richard J. Codey', 'Essex', 19588)
    error_count += spot_check_value(args, cv, 'Nicole Hagner', 'Morris', 9700)
    # District 28
    error_count += spot_check_value(args, cv, 'Russell Mollica', 'Essex', 4519)
    error_count += spot_check_value(args, cv, 'Carol Humphreys', 'Essex', 4607)
    # District 29
    error_count += spot_check_value(args, cv, 'M. Teresa Ruiz', 'Essex', 9076)
    error_count += spot_check_value(args, cv, 'L. Grace Spencer', 'Essex', 8572)
    # District 30
    error_count += spot_check_value(args, cv, 'Robert W. Singer', 'Monmouth', 13042)
    error_count += spot_check_value(args, cv, 'Shaun O\'Rourke', 'Ocean', 4124)
    # District 31
    error_count += spot_check_value(args, cv, 'Donnamarie James', 'Hudson', 2836)
    error_count += spot_check_value(args, cv, 'Daniel E. Beckelman', 'Hudson', 2751)
    # District 32
    error_count += spot_check_value(args, cv, 'Edward T. O\'Neill', 'Bergen', 501)
    error_count += spot_check_value(args, cv, 'April Tricoli-Busset', 'Hudson', 444)
    # District 33
    error_count += spot_check_value(args, cv, 'Brian P. Stack', 'Hudson', 20223)
    error_count += spot_check_value(args, cv, 'Sean Connors', 'Hudson', 17064)
    error_count += spot_check_value(args, cv, 'Christopher Garcia', 'Hudson', 3214)
    # District 34
    error_count += spot_check_value(args, cv, 'Ralph Bartnik', 'Essex', 1207)
    error_count += spot_check_value(args, cv, 'Joan Salensky', 'Passaic', 3105)
    # District 35
    error_count += spot_check_value(args, cv, 'Nellie Pou', 'Bergen', 2613)
    error_count += spot_check_value(args, cv, 'Donna Puglisi', 'Passaic', 2676)
    # District 36
    error_count += spot_check_value(args, cv, 'Donald E. DiOrio', 'Bergen', 10162)
    error_count += spot_check_value(args, cv, 'John C. Genovesi', 'Passaic', 691)
    # District 37
    error_count += spot_check_value(args, cv, 'Loretta Weinberg', 'Bergen', 23141)
    error_count += spot_check_value(args, cv, 'Julian Heickln', 'Bergen', 675)
    # District 38
    error_count += spot_check_value(args, cv, 'John J. Driscoll, Jr.', 'Bergen', 17831)
    error_count += spot_check_value(args, cv, 'Vinko Grskovic', 'Passaic', 64)
    # District 39
    error_count += spot_check_value(args, cv, 'Lorraine M. Waldes', 'Bergen', 14181)
    error_count += spot_check_value(args, cv, 'Clinton Bosca', 'Passaic', 148)
    # District 40
    error_count += spot_check_value(args, cv, 'John Zunic', 'Bergen', 4932)
    error_count += spot_check_value(args, cv, 'David C. Russo', 'Essex', 1358)
    error_count += spot_check_value(args, cv, 'Cassandra Lazzara', 'Morris', 1343)
    error_count += spot_check_value(args, cv, 'John Zunic', 'Passaic', 6883)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
