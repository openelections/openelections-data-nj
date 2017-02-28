#!/usr/bin/python

import sys
import argparse
import csv
from nj_common import *

def main():

    c_candidate_party = {}
    c_candidate_office = {}
    c_candidate_district = {}
    c_candidate_votes = {}

    args = handle_arguments()

    cfile = open_county_file()
    mfile = open_muni_file()

    process_county_file(args, cfile, c_candidate_office, c_candidate_district, c_candidate_party, c_candidate_votes)

def open_county_file():
    c_file_path = '../2016/20161108__nj__general.csv'
    f = open(c_file_path, 'rb')
    county_reader = csv.reader(f, delimiter = ',', quotechar = '"')
    return county_reader

def open_muni_file():
    m_file_path = '../2016/20161108__nj__general__municipal.csv'
    with open(m_file_path, 'rb') as csvfile:
        muni_reader = csv.reader(csvfile, delimiter = ',', quotechar = '"')
    return

def handle_arguments():
    arg_parser = argparse.ArgumentParser(description='Validate New Jersey 2016 county and muni data')
    arg_parser.add_argument('--verbose', '-v', dest='verbose',  help='report information verbosely', action='store_true')
    arg_parser.add_argument('--case', '-c', dest='case',  help='case sensitive text compare', action='store_true')
    return arg_parser.parse_args()

def verify_county_value(args, county_value):
    return_value = False
    compare_value = county_value.capitalize()
    if compare_value in CONST_COUNTIES:
        return_value = True
    return return_value

def verify_race_value(args, race_value):
    return_value = False
    compare_value = race_value.capitalize()
    if compare_value in CONST_RACES:
        return_value = True
    return return_value

def find_header_index(args, header_value, input_row):
    return_value = -1
    index = 0
    for value in input_row:
        if args.case:
            if value == header_value:
                return_value = index
        else:
            if value.upper() == header_value.upper():
                return_value = index
        index = index + 1
    return return_value

def validate_county_values(args, input_row, county_index):
    return_value = False
    if args.case:
        county_value = input_row[county_index].capitalize()
    else:
        county_value = input_row[county_index]
    if county_value in CONST_COUNTIES:
        return_value = True
    else:
        if args.verbose:
            print str(input_row[county_index]) + ' is not in the list of valid NJ Counties'
    return return_value

def validate_office_values(args, input_row, office_index):
    return_value = False
    if args.case:
        office_value = input_row[office_index].capitalize()
    else:
        office_value = input_row[office_index]
    if office_value in CONST_OFFICES:
        return_value = True
    else:
        if args.verbose:
            print str(input_row[office_index]) + ' is not in the list of valid NJ Offices'
    return return_value

def validate_district_values(args, input_row, district_index, office_index):
    return_value = False
    if args.case:
        district_value = input_row[district_index].capitalize()
        office_value = input_row[office_index].capitalize()
    else:
        district_value = input_row[district_index]
        office_value = input_row[office_index]
    if office_value.upper() == "U.S. HOUSE":
        if district_value in CONST_FEDERAL_DISTRICTS:
            return_value = True
    elif office_value.upper() == "GENERAL ASSEMBLY":
        if district_value in CONST_STATE_DISTRICTS:
            return_value = True
    elif office_value.upper() == "STATE SENATE":
        if district_value in CONST_STATE_DISTRICTS:
            return_value = True
    else:
        if district_value == "":
            return_value = True
    if return_value == False:
        if args.verbose:
            if office_value.upper() == "U.S. HOUSE":
                print str(input_row[district_index]) + ' is not in the list of valid Federal Districts'
            elif office_value.upper() == "GENERAL ASSEMBLY":
                print str(input_row[district_index]) + ' is not in the list of valid State Districts'
            elif office_value.upper() == "STATE SENATE":
                print str(input_row[district_index]) + ' is not in the list of valid State Districts'
            else:
                print 'The office of ' + office_value + ' should not contain a district value'
    return return_value

def process_county_file(args, in_file, candidate_office, candidate_district, candidate_party, candidate_votes):

    county_index = -1
    candidate_index = -1
    party_index = -1
    office_index = -1
    district_index = -1
    votes_index = -1

    found_error = False;
    error_count = 0;

    for row in in_file:
        if candidate_index == -1:
            county_index = find_header_index(args, "county", row)
            candidate_index = find_header_index(args, "candidate", row)
            office_index = find_header_index(args, "office", row)
            district_index = find_header_index(args, "district", row)
            party_index = find_header_index(args, "party", row)
            votes_index = find_header_index(args, "votes", row)
        else:
            found_error = False;
            if validate_county_values(args, row, county_index) == False:
                found_error = True;
            if validate_office_values(args, row, office_index) == False:
                found_error = True;
            if validate_district_values(args, row, district_index, office_index) == False:
                found_error = True;

        if found_error:
            error_count += 1

    print 'There were ' + str(error_count) + ' invalid values in the County File.'

    return

if __name__ == '__main__':
    main()
