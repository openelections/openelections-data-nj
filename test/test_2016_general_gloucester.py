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
    CONST_PRECINCT_FILE = '../2016/20161108__nj__general__gloucester__precinct.csv'

    args = handle_arguments()
    process_precinct_file(args, CONST_PRECINCT_FILE)
    compare_county_and_precinct_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_PRECINCT_FILE)
    #spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2016 Gloucester county data')
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

    county_name = 'Gloucester'
    county_votes = cv.get_all_candidates_and_votes_by_county(county_name)
    for cand in county_votes:
        if cand == 'Hillary Rodham Clinton':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'HILLARY RODHAM CLINTON')
        elif cand == 'Donald J. Trump':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'DONALD J. TRUMP')
        elif cand == 'Monica Moorehead':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'MONICA MOOREHEAD')
        elif cand == 'Darrell Castle':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'DARRELL CASTLE')
        elif cand == 'Alyson Kennedy':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'ALYSON KENNEDY')
        elif cand == 'Jill Stein':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'JILL STEIN')
        elif cand == 'Gloria La Riva':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'GLORIA LA RIVA')
        elif cand == 'Gary Johnson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'GARY JOHNSON')
        elif cand == 'Bob Patterson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'BOB PATTERSON')
        elif cand == 'Donald W. Norcross':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'DONALD W. NORCROSS')
        elif cand == 'Scot John Tomaszewski':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'SCOT JOHN TOMASZEWSKI')
        elif cand == 'Michael Berman':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'MICHAEL BERMAN')
        elif cand == 'William F. Sihr IV':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'WILLIAM F. SIHR IV')
        elif cand == 'Frank A. LoBiondo':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'FRANK A. LOBIONDO')
        elif cand == 'David H. Cole':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'DAVID H. COLE')
        elif cand == 'Eric Beechwood':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'ERIC BEECHWOOD')
        elif cand == 'Steven Fenichel':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'STEVEN FENICHEL')
        elif cand == 'James Keenan':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'JAMES KEENAN')
        elif cand == 'Gabriel Brian Franco':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'GABRIEL BRIAN FRANCO')
        elif cand == 'John Ordille':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'JOHN ORDILLE')
        elif cand == 'Rocky Roque De la Fuente':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'ROCKY ROQUE DE LA FUENTE')
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
