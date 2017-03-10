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
import csv
from collections import defaultdict

CONST_COUNTIES = [ 'Atlantic', 
                   'Bergen', 
                   'Burlington', 
                   'Camden', 
                   'Cape May', 
                   'Cumberland', 
                   'Essex', 
                   'Gloucester', 
                   'Hudson', 
                   'Hunterdon', 
                   'Mercer', 
                   'Middlesex', 
                   'Monmouth', 
                   'Morris', 
                   'Ocean', 
                   'Passaic', 
                   'Salem', 
                   'Somerset', 
                   'Sussex', 
                   'Union', 
                   'Warren' ]

CONST_OFFICES = [ 'President',
                  'U.S. House',
                  'U.S. Senate',
                  'State Senate',
                  'General Assembly' ]

CONST_FEDERAL_DISTRICTS = [ "1", 
                            "2",
                            "3",
                            "4",
                            "5",
                            "6",
                            "7",
                            "8",
                            "9",
                            "10",
                            "11",
                            "12" ]

CONST_STATE_DISTRICTS = [ "1", 
                          "2",
                          "3",
                          "4",
                          "5",
                          "6",
                          "7",
                          "8",
                          "9",
                          "10",
                          "11",
                          "12",
                          "13",
                          "14",
                          "15",
                          "16",
                          "17",
                          "18",
                          "19",
                          "20",
                          "21",
                          "22",
                          "23",
                          "24",
                          "25",
                          "26",
                          "27",
                          "28",
                          "29",
                          "30",
                          "31",
                          "32",
                          "33",
                          "34",
                          "35",
                          "36",
                          "37",
                          "38",
                          "39",
                          "40" ]

def is_number(test_value):
    try:
        float(test_value)
        return True
    except ValueError:
        return False

class VerifyBase:

    def __init__(self, file_name, verbose, case):
        self.file_name = file_name
        self.verbose = verbose
        self.ignore_case = case
        self.candidate_index = -1
        self.party_index = -1
        self.office_index = -1
        self.district_index = -1
        self.votes_index = -1
        self.c_file = open(self.file_name, 'rb')
        self.c_reader = csv.reader(self.c_file, delimiter = ',', quotechar = '"')
        self.__calc_base_column_indexes()

    def get_candidate_index(self):
        return self.candidate_index

    def get_party_index(self):
        return self.party_index

    def get_office_index(self):
        return self.office_index

    def get_district_index(self):
        return self.district_index

    def get_votes_index(self):
        return self.votes_index

    def find_header_index(self, header_value, input_row):
        return_value = -1
        index = 0
        for value in input_row:
            if self.ignore_case:
                if value == header_value:
                    return_value = index
            else:
                if value.upper() == header_value.upper():
                    return_value = index
            index += 1
        return return_value

    def __calc_base_column_indexes(self):
    
        for row in self.c_reader:
            if self.candidate_index == -1:
                self.candidate_index = self.find_header_index("candidate", row)
            if self.office_index == -1:
                self.office_index = self.find_header_index("office", row)
            if self.district_index == -1:
                self.district_index = self.find_header_index("district", row)
            if self.party_index == -1:
                self.party_index = self.find_header_index("party", row)
            if self.votes_index == -1:
                self.votes_index = self.find_header_index("votes", row)

    def __verify_office_value(self, office_value):
        return_value = False
        if self.ignore_case:
            compare_value = office_value.capitalize()
        else:
            compare_value = office_value
        if compare_value in CONST_OFFICES:
            return_value = True
        else:
            if self.verbose:
                print office_value + ' is not in the list of valid NJ Offices'
        return return_value

    def __verify_district_value(self, district_value, office_value):
        return_value = False
        if self.ignore_case:
            compare_district = district_value.capitalize()
            compare_office = office_value.capitalize()
        else:
            compare_district = district_value
            compare_office = office_value
        if compare_office.upper() == "U.S. HOUSE":
            if compare_district in CONST_FEDERAL_DISTRICTS:
                return_value = True
        elif compare_office.upper() == "GENERAL ASSEMBLY":
            if compare_district in CONST_STATE_DISTRICTS:
                return_value = True
        elif compare_office.upper() == "STATE SENATE":
            if compare_district in CONST_STATE_DISTRICTS:
                return_value = True
        else:
            if compare_district == "":
                return_value = True
        if return_value == False:
            if self.verbose:
                if compare_office.upper() == "U.S. HOUSE" or \
                   compare_office.upper() == "GENERAL ASSEMBLY" or \
                   compare_office.upper() == "STATE SENATE":
                    print '[' + compare_district + '] is not a valid district for the office of ' \
                          + compare_office
                else:
                    print 'The office of ' + compare_office + ' should not contain a district value'
        return return_value

    def __verify_votes_value(self, votes_value):
        return_value = is_number(votes_value)
        if return_value == False:
            if self.verbose:
                print 'Invalid number found as a vote total [' + votes_value + ']'
        return return_value

    def verify_offices(self):
        office_errors = 0
        self.c_file.seek(0)
        for i, row in enumerate(self.c_reader):
            if i > 0:
                if self.__verify_office_value(row[self.get_office_index()]) == False:
                    office_errors += 1
        return office_errors

    def verify_districts(self):
        district_errors = 0
        self.c_file.seek(0)
        for i, row in enumerate(self.c_reader):
            if i > 0:
                if self.__verify_district_value(row[self.get_district_index()],
                                                row[self.get_office_index()]) == False:
                    district_errors += 1
        return district_errors

    def verify_votes(self):
        votes_errors = 0
        self.c_file.seek(0)
        for i, row in enumerate(self.c_reader):
            if i > 0:
                if self.__verify_votes_value(row[self.get_votes_index()]) == False:
                    votes_errors += 1
        return votes_errors

    def verify_candidate_district_relationship(self):

        cand_district_dict = defaultdict(list)
        error_count = 0

        self.c_file.seek(0)
        for row in self.c_reader:
           candidate = row[self.get_candidate_index()]
           district = row[self.get_district_index()]

           if candidate in cand_district_dict:
               if district not in cand_district_dict[candidate]:
                   cand_district_dict[candidate].append(district)
           else:
               cand_district_dict[candidate].append(district)

        for candidate in cand_district_dict:
            if len(cand_district_dict[candidate]) > 1:
                error_count += 1
                if self.verbose:
                    print candidate + ' is associated to multiple districts: ' + \
                                      str(cand_district_dict[candidate])
        return error_count

    def verify_candidate_office_relationship(self):

        cand_office_dict = defaultdict(list)
        error_count = 0

        self.c_file.seek(0)
        for row in self.c_reader:
           candidate = row[self.get_candidate_index()]
           office = row[self.get_office_index()]

           if candidate in cand_office_dict:
               if office not in cand_office_dict[candidate]:
                   cand_office_dict[candidate].append(office)
           else:
               cand_office_dict[candidate].append(office)

        for candidate in cand_office_dict:
            if len(cand_office_dict[candidate]) > 1:
                error_count += 1
                if self.verbose:
                    print candidate + ' is associated to multiple offices: ' + \
                                      str(cand_office_dict[candidate])
        return error_count

    def verify_candidate_party_relationship(self):

        cand_party_dict = defaultdict(list)
        error_count = 0

        self.c_file.seek(0)
        for row in self.c_reader:
           candidate = row[self.get_candidate_index()]
           party = row[self.get_party_index()]

           if candidate in cand_party_dict:
               if party not in cand_party_dict[candidate]:
                   cand_party_dict[candidate].append(party)
           else:
               cand_party_dict[candidate].append(party)

        for candidate in cand_party_dict:
            if len(cand_party_dict[candidate]) > 1:
                error_count += 1
                if self.verbose:
                    print candidate + ' is associated to multiple parties: ' + \
                                      str(cand_party_dict[candidate])
        return error_count

class VerifyCounty(VerifyBase):

    def __init__ (self, file_name, verbose, ignore_case):
        VerifyBase.__init__(self, file_name, verbose, ignore_case)
        self.county_index = -1
        self.__calc_county_column_indexes()

    def __calc_county_column_indexes(self):
   
        self.c_file.seek(0)
        for row in self.c_reader:
            if self.county_index == -1:
                self.county_index = self.find_header_index("county", row)

    def __verify_county_value(self, county_value):
        return_value = False
        if self.ignore_case:
            compare_value = county_value.capitalize()
        else:
            compare_value = county_value
        if compare_value in CONST_COUNTIES:
            return_value = True
        else:
            if self.verbose:
                print county_value + ' is not in the list of valid NJ Counties'
        return return_value

    def get_county_index(self):
        return self.county_index

    def verify_counties(self):
        county_errors = 0
        self.c_file.seek(0)
        for i, row in enumerate(self.c_reader):
            if i > 0:
                if self.__verify_county_value(row[self.get_county_index()]) == False:
                    county_errors += 1
        return county_errors

    def get_all_candidates_and_votes_by_county(self, in_county_name):
        cand_vote_dict = defaultdict(int)

        self.c_file.seek(0)
        for i, row in enumerate(self.c_reader):
           if i > 0:
               county_name = row[self.get_county_index()]
               candidate = row[self.get_candidate_index()]
               votes = int(row[self.get_votes_index()])

               if county_name == in_county_name:
                   if candidate in cand_vote_dict:
                       cand_vote_dict[candidate] += votes
                   else:
                       cand_vote_dict[candidate] = votes

        return cand_vote_dict
        
    def get_candidates_votes_by_county(self, in_county_name, in_candidate_name):

        return_value = 0

        self.c_file.seek(0)
        for i, row in enumerate(self.c_reader):
            if i > 0:
               county_name = row[self.get_county_index()]
               candidate = row[self.get_candidate_index()]
               votes = int(row[self.get_votes_index()])

               if county_name == in_county_name and candidate == in_candidate_name:
                   return_value += votes                

        return return_value

class VerifyMuni(VerifyCounty):

    def __init__ (self, file_name, verbose, ignore_case):
        VerifyCounty.__init__(self, file_name, verbose, ignore_case)
        self.muni_index = -1
        self.__calc_muni_column_indexes()

    def __calc_muni_column_indexes(self):
        self.c_file.seek(0)
        for row in self.c_reader:
            if self.muni_index == -1:
                self.muni_index = self.find_header_index("municipality", row)
        
    def get_muni_index(self):
        return self.muni_index

