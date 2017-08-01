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

    CONST_COUNTY_FILE = '../2016/20161108__nj__general.csv'
    CONST_PRECINCT_FILE = '../2016/20161108__nj__general__union__precinct.csv'

    args = handle_arguments()
    process_precinct_file(args, CONST_PRECINCT_FILE)
    compare_county_and_precinct_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_PRECINCT_FILE)
    #spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2016 Union county data')
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
    error_count += verifier.verify_candidate_party_relationship()
    error_count += verifier.verify_candidate_office_relationship()
    error_count += verifier.verify_candidate_district_relationship()

    print 'There were ' + str(error_count) + ' invalid values in the Precinct File.'

    return

def compare_county_and_precinct_totals(args, county_file, precinct_file):

    error_count = 0

    cv = VerifyCounty(county_file, args.verbose, args.case)
    mv = VerifyPrecinct(precinct_file, args.verbose, args.case)

    county_name = 'Union'
    county_votes = cv.get_all_candidates_and_votes_by_county(county_name)
    for cand in county_votes:
        if cand == 'Hillary Rodham Clinton':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Hillary Rodham CLINTON Timothy Michael KAINE')
        elif cand == 'Donald J. Trump':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Donald J. TRUMP Michael R. PENCE')
        elif cand == 'Alyson Kennedy':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Alyson KENNEDY Osborne HART')
        elif cand == 'Darrell Castle':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Darrell CASTLE Scott BRADLEY')
        elif cand == 'Rocky Roque De la Fuente':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Rocky Roque DE LA FUENTE Michael STEINBERG')
        elif cand == 'Jill Stein':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Jill STEIN Ajamu BARAKA')
        elif cand == 'Gloria La Riva':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Gloria LA RIVA Eugene PURYEAR')
        elif cand == 'Monica Moorehead':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Monica MOOREHEAD Lamont LILLY')
        elif cand == 'Gary Johnson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Gary JOHNSON William WELD')
        elif cand == 'Peter Jacob':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Peter JACOB')
        elif cand == 'Leonard Lance':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Leonard LANCE')
        elif cand == 'Arthur T. Haussmann Jr.':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Arthur T. HAUSSMANN, JR.')
        elif cand == 'Dan O\'Neill':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Dan O\'NEILL')
        elif cand == 'Albio Sires':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Albio SIRES')
        elif cand == 'Agha Khan':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Agha KHAN')
        elif cand == 'Pablo Olivera':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Pablo OLIVERA')
        elif cand == 'Dan Delaney':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Dan DELANEY')
        elif cand == 'Donald M. Payne Jr.':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Donald M. PAYNE, JR.')
        elif cand == 'David H. Pinckney':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'David H. PINCKNEY')
        elif cand == 'Joanne Miller':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joanne MILLER')
        elif cand == 'Aaron Walter Fraser':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Aaron Walter FRASER')
        elif cand == 'Bonnie Watson Coleman':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Bonnie WATSON COLEMAN')
        elif cand == 'Steven J. Uccio':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Steven J. UCCIO')
        elif cand == 'Michael R. Bollentin':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Michael R. BOLLENTIN')
        elif cand == 'Steven Welzer':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Steven WELZER')
        elif cand == 'R. Edward Forchion':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'R. Edward FORCHION')
        elif cand == 'Thomas Fitzpatrick':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Thomas FITZPATRICK')
        elif cand == 'Robert Shapiro':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Robert SHAPIRO')
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
