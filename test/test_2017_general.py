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

    CONST_COUNTY_FILE = '../2017/20171107__nj__general__county.csv'
    CONST_MUNI_FILE = '../2017/20171107__nj__general__municipal.csv'

    args = handle_arguments()
    process_county_file(args, CONST_COUNTY_FILE)
    process_muni_file(args, CONST_MUNI_FILE)
    compare_county_and_muni_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_MUNI_FILE)
    spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2017 General Election county and muni data')
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
    error_count += spot_check_value(args, cv, 'Jeff Van Drew', 'Atlantic', 1130)
    error_count += spot_check_value(args, cv, 'Bob Andrzejczak', 'Cape May', 18003)
    error_count += spot_check_value(args, cv, 'James R. Sauro', 'Cumberland', 8759)
    error_count += spot_check_value(args, cv, 'Colin Bell', 'Atlantic', 23406)
    error_count += spot_check_value(args, cv, 'John J. Burzichelli', 'Cumberland', 2690)
    error_count += spot_check_value(args, cv, 'Philip J. Donohue', 'Gloucester', 12021)
    error_count += spot_check_value(args, cv, 'Edward R. Durr', 'Salem', 0)
    error_count += spot_check_value(args, cv, 'Fred H. Madden', 'Camden', 22287)
    error_count += spot_check_value(args, cv, 'Patricia Jefferson Kline', 'Gloucester', 9341)
    error_count += spot_check_value(args, cv, 'Mohammad Kabir', 'Camden', 314)
    error_count += spot_check_value(args, cv, 'Kevin Ehret', 'Gloucester', 7645)
    error_count += spot_check_value(args, cv, 'James Beach', 'Burlington', 2188)
    error_count += spot_check_value(args, cv, 'Monica Sohler', 'Camden', 786)
    error_count += spot_check_value(args, cv, 'Carol Murphy', 'Burlington',38819 )
    error_count += spot_check_value(args, cv, 'George B. Youngkin', 'Atlantic', 1404)
    error_count += spot_check_value(args, cv, 'Ryan Peters', 'Burlington',23440 )
    error_count += spot_check_value(args, cv, 'Maryann Merlino', 'Camden', 3554)
    error_count += spot_check_value(args, cv, 'Christopher J. Connors', 'Atlantic', 4675)
    error_count += spot_check_value(args, cv, 'Brian E. Rumpf', 'Burlington', 1736)
    error_count += spot_check_value(args, cv, 'Jill Dobrowansky', 'Ocean', 18017)
    error_count += spot_check_value(args, cv, 'Dave Wolfe', 'Ocean', 39265)
    error_count += spot_check_value(args, cv, 'Vin Gopal', 'Monmouth', 31308)
    error_count += spot_check_value(args, cv, 'David H. Lande', 'Burlington', 1401)
    error_count += spot_check_value(args, cv, 'Kevin Antoine', 'Middlesex', 277)
    error_count += spot_check_value(args, cv, 'Robert D. Clifton', 'Monmouth', 11215)
    error_count += spot_check_value(args, cv, 'Daniel A. Krause', 'Ocean', 403)
    error_count += spot_check_value(args, cv, 'Declan O\'Scanlon', 'Monmouth', 34976)
    error_count += spot_check_value(args, cv, 'Ileana Schirmer', 'Mercer', 15912)
    error_count += spot_check_value(args, cv, 'Daniel R. Benson', 'Middlesex', 13271)
    error_count += spot_check_value(args, cv, 'Shirley K. Turner', 'Hunterdon', 2654)
    error_count += spot_check_value(args, cv, 'Emily Rich', 'Mercer', 11104)
    error_count += spot_check_value(args, cv, 'Laurie Poppe', 'Hunterdon', 6017)
    error_count += spot_check_value(args, cv, 'Andrew Zwicker', 'Mercer', 6715)
    error_count += spot_check_value(args, cv, 'Donna M. Simon', 'Middlesex', 3438)
    error_count += spot_check_value(args, cv, 'Mark Caliguire', 'Somerset', 14713)
    error_count += spot_check_value(args, cv, 'Bob Smith', 'Middlesex', 18113)
    error_count += spot_check_value(args, cv, 'Robert A. Quinn', 'Somerset', 4595)
    error_count += spot_check_value(args, cv, 'April Bengivenga', 'Middlesex', 17559)
    error_count += spot_check_value(args, cv, 'Lewis Glogower', 'Middlesex', 16860)
    error_count += spot_check_value(args, cv, 'Joseph F. Vitale', 'Middlesex', 27681)
    error_count += spot_check_value(args, cv, 'Yvonne Lopez', 'Middlesex', 24830)
    error_count += spot_check_value(args, cv, 'Ashraf Hanna', 'Union', 5023)
    error_count += spot_check_value(args, cv, 'Joseph G. Aubourg', 'Union', 5361)
    error_count += spot_check_value(args, cv, 'Thomas H. Kean Jr.', 'Morris', 3421)
    error_count += spot_check_value(args, cv, 'Jon Bramnick', 'Somerset', 8846)
    error_count += spot_check_value(args, cv, 'Lacey Rzeszowski', 'Union', 23936)
    error_count += spot_check_value(args, cv, 'Joseph A. Bonilla', 'Middlesex', 2501)
    error_count += spot_check_value(args, cv, 'James J. Kennedy', 'Somerset', 3189)
    error_count += spot_check_value(args, cv, 'Onel Martinez', 'Union', 808)
    error_count += spot_check_value(args, cv, 'Christine Lui Chen', 'Hunterdon', 8659)
    error_count += spot_check_value(args, cv, 'Laura Shaw', 'Somerset', 9495)
    error_count += spot_check_value(args, cv, 'Michael Estrada', 'Warren', 396)
    error_count += spot_check_value(args, cv, 'Steven V. Oroho', 'Morris', 3332)
    error_count += spot_check_value(args, cv, 'Harold J. Wirths', 'Sussex', 22262)
    error_count += spot_check_value(args, cv, 'Aaron Hyndman', 'Warren', 364)
    error_count += spot_check_value(args, cv, 'Lisa Bhimani', 'Morris', 26975)
    error_count += spot_check_value(args, cv, 'Richard Corcoran', 'Somerset', 1131)
    error_count += spot_check_value(args, cv, 'Joe Pennacchio', 'Essex', 5278)
    error_count += spot_check_value(args, cv, 'Jay Webber', 'Morris', 22407)
    error_count += spot_check_value(args, cv, 'E. William Edge', 'Passaic', 2594)
    error_count += spot_check_value(args, cv, 'Richard Codey', 'Essex', 32800)
    error_count += spot_check_value(args, cv, 'Angelo Tedesco Jr.', 'Morris', 11012)
    error_count += spot_check_value(args, cv, 'Ronald L. Rice', 'Essex', 31774)
    error_count += spot_check_value(args, cv, 'Veronica Branch', 'Essex', 4839)
    error_count += spot_check_value(args, cv, 'M. Teresa Ruiz', 'Essex', 20506)
    error_count += spot_check_value(args, cv, 'Shanique Speight', 'Essex', 18308)
    error_count += spot_check_value(args, cv, 'Troy Knight-Napper', 'Essex', 1306)
    error_count += spot_check_value(args, cv, 'Veronica Branch', 'Essex', 4839)
    error_count += spot_check_value(args, cv, 'Robert W. Singer', 'Monmouth', 19895)
    error_count += spot_check_value(args, cv, 'Sean T. Kean', 'Ocean', 11719)
    error_count += spot_check_value(args, cv, 'Sandra B. Cunningham', 'Hudson', 25437)
    error_count += spot_check_value(args, cv, 'Nicholas Chiaravalloti', 'Hudson', 22823)
    error_count += spot_check_value(args, cv, 'Nicholas J. Sacco', 'Bergen', 2461)
    error_count += spot_check_value(args, cv, 'Bartholomew J. Talamini', 'Hudson', 4682)
    error_count += spot_check_value(args, cv, 'Brian P. Stack', 'Hudson', 36594)
    error_count += spot_check_value(args, cv, 'Raj Mukherji', 'Hudson', 31997)
    error_count += spot_check_value(args, cv, 'Nia H. Gill', 'Essex', 25779)
    error_count += spot_check_value(args, cv, 'Sheila Y. Oliver', 'Passaic', 8487)
    error_count += spot_check_value(args, cv, 'Nelida Pou', 'Bergen', 4563)
    error_count += spot_check_value(args, cv, 'Nihad Younes', 'Passaic', 3092)
    error_count += spot_check_value(args, cv, 'Paul A. Sarlo', 'Bergen', 19484)
    error_count += spot_check_value(args, cv, 'Gary Schaer', 'Passaic', 4588)
    error_count += spot_check_value(args, cv, 'Modesto Romero', 'Bergen', 10788)
    error_count += spot_check_value(args, cv, 'Claudio I. Belusic', 'Bergen', 392)
    error_count += spot_check_value(args, cv, 'Bob Gordon', 'Bergen', 28613)
    error_count += spot_check_value(args, cv, 'William Leonard', 'Passaic', 2147)
    error_count += spot_check_value(args, cv, 'Gerald Cardinale', 'Bergen', 29342)
    error_count += spot_check_value(args, cv, 'Jannie Chung', 'Passaic', 4163)
    error_count += spot_check_value(args, cv, 'Kristin M. Corrado', 'Bergen', 12817)
    error_count += spot_check_value(args, cv, 'Thomas Duch', 'Essex', 1411)
    error_count += spot_check_value(args, cv, 'Paul Vagianos', 'Morris', 2414)
    error_count += spot_check_value(args, cv, 'Anthony J. Pellechia', 'Passaic', 478)
    error_count += spot_check_value(args, cv, 'Philip Murphy - Shelia Oliver', 'Atlantic', 36952)
    error_count += spot_check_value(args, cv, 'Kim Guadagno - Carlos A. Rendo', 'Bergen', 94904)
    error_count += spot_check_value(args, cv, 'Gina Genovese - Lt. Governor Not Filed', 'Burlington', 465)
    error_count += spot_check_value(args, cv, 'Peter J. Rohrman - Karese J. Laguerre', 'Camden', 876)
    error_count += spot_check_value(args, cv, 'Seth Kaper-Dale - Lisa Durden', 'Cape May', 119)
    error_count += spot_check_value(args, cv, 'Matthew Riccardi - Lt. Governor Not Filed', 'Cumberland', 149)
    error_count += spot_check_value(args, cv, 'Vincent Ross - April A. Johnson', 'Essex', 174)
    error_count += spot_check_value(args, cv, 'Philip Murphy - Shelia Oliver', 'Gloucester', 42349)
    error_count += spot_check_value(args, cv, 'Kim Guadagno - Carlos A. Rendo', 'Hudson', 19236)
    error_count += spot_check_value(args, cv, 'Gina Genovese - Lt. Governor Not Filed', 'Hunterdon', 265)
    error_count += spot_check_value(args, cv, 'Peter J. Rohrman - Karese J. Laguerre', 'Mercer', 399)
    error_count += spot_check_value(args, cv, 'Seth Kaper-Dale - Lisa Durden', 'Middlesex', 1606)
    error_count += spot_check_value(args, cv, 'Matthew Riccardi - Lt. Governor Not Filed', 'Monmouth', 746)
    error_count += spot_check_value(args, cv, 'Vincent Ross - April A. Johnson', 'Morris', 440)
    error_count += spot_check_value(args, cv, 'Philip Murphy - Shelia Oliver', 'Ocean', 56582)
    error_count += spot_check_value(args, cv, 'Kim Guadagno - Carlos A. Rendo', 'Passaic', 36230)
    error_count += spot_check_value(args, cv, 'Gina Genovese - Lt. Governor Not Filed', 'Salem', 431)
    error_count += spot_check_value(args, cv, 'Peter J. Rohrman - Karese J. Laguerre', 'Somerset', 413)
    error_count += spot_check_value(args, cv, 'Seth Kaper-Dale - Lisa Durden', 'Sussex', 331)
    error_count += spot_check_value(args, cv, 'Matthew Riccardi - Lt. Governor Not Filed', 'Union', 562)
    error_count += spot_check_value(args, cv, 'Vincent Ross - April A. Johnson', 'Warren', 154)

    print "There are " + str(error_count) + " Spot Check errors"

if __name__ == '__main__':
    main()
