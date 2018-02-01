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
    CONST_PRECINCT_FILE = '../2017/20171107__nj__general__union__precinct.csv'

    args = handle_arguments()
    process_precinct_file(args, CONST_PRECINCT_FILE)
    compare_county_and_precinct_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_PRECINCT_FILE)
    #spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2017 Union county data')
    arg_parser.add_argument('--verbose', '-v', dest='verbose',  help='report information verbosely', action='store_true')
    arg_parser.add_argument('--case', '-c', dest='case',  help='case sensitive text compare', action='store_true')
    return arg_parser.parse_args()

def process_precinct_file(args, in_file):

    error_count = 0

    verifier = VerifyMuni(in_file, args.verbose, args.case)   
    error_count += verifier.verify_counties()
    error_count += verifier.verify_offices()
    error_count += verifier.verify_districts()
    error_count += verifier.verify_votes()
    #error_count += verifier.verify_candidate_party_relationship()
    #error_count += verifier.verify_candidate_office_relationship()
    #error_count += verifier.verify_candidate_district_relationship()

    print 'There were ' + str(error_count) + ' invalid values in the Precinct File.'

    return

def compare_county_and_precinct_totals(args, county_file, precinct_file):

    error_count = 0

    cv = VerifyCounty(county_file, args.verbose, args.case)
    mv = VerifyPrecinct(precinct_file, args.verbose, args.case)

    county_name = 'Union'
    county_votes = cv.get_all_candidates_and_votes_by_county(county_name)
    for cand in county_votes:
        if cand == 'Philip Murphy - Shelia Oliver':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Philip MURPHY, Sheila OLIVER')
        elif cand == 'Kim Guadagno - Carlos A. Rendo':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Kim GUADAGNO, Carlos A. RENDO')
        elif cand == 'Gina Genovese - Lt. Governor Not Filed':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Gina GENOVESE')
        elif cand == 'Peter J. Rohrman - Karese J. Laguerre':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Peter J. ROHRMAN, Karese J. LAGUERRE')
        elif cand == 'Seth Kaper-Dale - Lisa Durden':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Seth KAPER-DALE, Lisa DURDEN')
        elif cand == 'Matthew Riccardi - Lt. Governor Not Filed':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Matthew RICCARDI')
        elif cand == 'Vincent Ross - April A. Johnson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Vincent ROSS, April A. JOHNSON')
        elif cand == 'Joseph P. Cryan':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joseph P. CRYAN')
        elif cand == 'Ashraf Hanna':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Ashraf HANNA')
        elif cand == 'Jill Lazare':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Jill LAZARE')
        elif cand == 'Thomas H. Kean Jr.':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Thomas H. KEAN, JR.')
        elif cand == 'Bruce H. Bergen':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Bruce H. BERGEN')
        elif cand == 'Lacey Rzeszowski':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Lacey RZESZOWSKI')
        elif cand == 'Jon Bramnick':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Jon BRAMNICK')
        elif cand == 'Nancy F. Munoz':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Nancy F. MUNOZ')
        elif cand == 'Annette Quijano':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Annette QUIJANO')
        elif cand == 'Jamel C. Holley':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Jamel C. HOLLEY')
        elif cand == 'Richard S. Fortunato':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Richard S. FORTUNATO')
        elif cand == 'John Quattrocchi':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'John QUATTROCCHI')
        elif cand == 'Joseph G. Aubourg':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joseph G. AUBOURG')
        elif cand == 'Joseph A. Bonilla':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joseph A. BONILLA')
        elif cand == 'Nicholas P. Scutari':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Nicholas P. SCUTARI')
        elif cand == 'Gerald \"Jerry\" Green':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Gerald Jerry GREEN')
        elif cand == 'James J. Kennedy':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'James J. KENNEDY')
        elif cand == 'Onel Martinez':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Onel MARTINEZ')
        elif cand == 'Sumantha Prasad':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Sumantha PRASAD')
        else:
            muni_total = mv.get_candidates_votes_by_county(county_name, cand)
        if muni_total != county_votes[cand]:
            error_count += 1
            if args.verbose:
                print "Total votes are different in County (" + \
                      str(county_votes[cand]) + ") and Precinct (" + \
                      str(muni_total) + ") for " + cand + " in " + \
                      county_name + " County."

    print "There are " + str(error_count) + " vote totals that are not reconciled."

if __name__ == '__main__':
    main()
