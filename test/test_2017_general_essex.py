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
    CONST_PRECINCT_FILE = '../2017/20171107__nj__general__essex__precinct.csv'

    args = handle_arguments()
    process_precinct_file(args, CONST_PRECINCT_FILE)
    compare_county_and_precinct_totals(args, 
                                   CONST_COUNTY_FILE,
                                   CONST_PRECINCT_FILE)
    #spot_check_totals(args, CONST_COUNTY_FILE)

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2017 Essex county data')
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

    county_name = 'Essex'
    county_votes = cv.get_all_candidates_and_votes_by_county(county_name)
    for cand in county_votes:
        if cand == 'Philip Murphy - Shelia Oliver':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'MURPHY / OLIVER')
        elif cand == 'Kim Guadagno - Carlos A. Rendo':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'GUADAGNO / RENDO')
        elif cand == 'Gina Genovese - Lt. Governor Not Filed':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'GENOVESE /')
        elif cand == 'Peter J. Rohrman - Karese J. Laguerre':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'ROHRMAN / LAGUERRE')
        elif cand == 'Seth Kaper-Dale - Lisa Durden':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'KAPER-DALE / DURDEN')
        elif cand == 'Matthew Riccardi - Lt. Governor Not Filed':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'RICCARDI /')
        elif cand == 'Vincent Ross - April A. Johnson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'ROSS / JOHNSON')
        elif cand == 'Elliot Isibor':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Elliot ISIBOR')
        elif cand == 'Joe Pennacchio':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joe PENNACCHIO')
        elif cand == 'Richard Codey':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Richard CODEY')
        elif cand == 'Pasquale Capozzoli':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Pasquale CAPOZZOLI')
        elif cand == 'Ronald L. Rice':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Ronald L. RICE')
        elif cand == 'Troy Knight-Napper':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Troy KNIGHT-NAPPER')
        elif cand == 'M. Teresa Ruiz':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'M. Teresa RUIZ')
        elif cand == 'Maria E. Lopez':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Maria E. LOPEZ')
        elif cand == 'Pablo Olivera':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Pablo OLIVERA')
        elif cand == 'Nia H. Gill':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Nia H. GILL')
        elif cand == 'Mahir Saleh':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Mahir SALEH')
        elif cand == 'Thomas Duch':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Thomas DUCH')
        elif cand == 'Kristin M. Corrado':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Kristin M. CORRADO')
        elif cand == 'Joseph R. Raich':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joseph R. RAICH')
        elif cand == 'E. William Edge':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'E. William EDGE')
        elif cand == 'Jay Webber':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Jay WEBBER')
        elif cand == 'BettyLou DeCroce':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Bettylou DeCROCE')
        elif cand == 'John F. McKeon':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'John F. McKEON')
        elif cand == 'Mila M. Jasey':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Mila M. JASEY')
        elif cand == 'Ronald DeRose':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Ronald DeROSE')
        elif cand == 'Angelo Tedesco Jr.':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Angelo TEDESCO, Jr.')
        elif cand == 'Ralph R. Caputo':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Ralph R. CAPUTO')
        elif cand == 'Cleopatra G. Tucker':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Cleopatra G. TUCKER')
        elif cand == 'James Boydston':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'James BOYDSTON')
        elif cand == 'Veronica Branch':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Veronica BRANCH')
        elif cand == 'Joanne Miller':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Joanne MILLER')
        elif cand == 'Scott Thomas Nicastro Jr.':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Scott Thomas NICASTRO, Jr.')
        elif cand == 'Eliana Pintor Marin':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Eliana PINTOR MARIN')
        elif cand == 'Shanique Speight':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Shanique SPEIGHT')
        elif cand == 'Jeannette Veras':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Jeannette VERAS')
        elif cand == 'Charles G. Hood':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Charles G. HOOD')
        elif cand == 'Sheila Y. Oliver':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Sheila OLIVER')
        elif cand == 'Thomas P. Giblin':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Thomas P. GIBLIN')
        elif cand == 'Nicholas G. Surgent':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Nicholas G. SURGENT')
        elif cand == 'Tafari Anderson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Tafari ANDERSON')
        elif cand == 'Christine Ordway':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Christine ORDWAY')
        elif cand == 'Paul Vagianos':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Paul VAGIANOS')
        elif cand == 'Christopher P. DePhillips':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Christopher P. DePHILLIPS')
        elif cand == 'Kevin J. Rooney':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Kevin J. ROONEY')
        elif cand == 'Anthony J. Pellechia':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Anthony J. PELLECHIA')
        elif cand == 'Patricia Sebold':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Patricia SEBOLD')
        elif cand == 'Rufus I. Johnson':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Rufus I. JOHNSON')
        elif cand == 'Brendan W. Gill':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Brendan W. GILL')
        elif cand == 'Lebby C. Jones':
            muni_total = mv.get_candidates_votes_by_county(county_name, 'Lebby C. JONES')
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
