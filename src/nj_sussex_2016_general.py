#!/usr/bin/python
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
import os.path
import csv
from lxml.html import fromstring
import lxml.html as PARSER
import re


class LineType:
    TOWN = 1
    RACE = 2
    VOTEFOR = 3
    CANDIDATE = 4
    OTHER = 10

class ContestRecord (object):

    def __init__ (self, xmlKey, county, office, district):
        self.county = county
        self.xmlKey = xmlKey
        self.office = office
        self.district = district
        self.party = ''
        self.precinct = ''
        self.candidate = ''
        self.votes = 0

    def printCSVLine(self, outFile):
        outFile.writerow( (self.county, self.precinct, self.office, self.district, self.candidate, self.party, self.votes) )
        return

def validateArgs( p_args ):
    return

def openOutputFile(outputPath):
    try:
        f = open( outputPath, 'w') 
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    except:
        sys.exit('ERROR: Could not open output file: ' + outputPath)
    return writer

def printLine(current_line, line_type):
    if line_type == LineType.TOWN:
        print "TOWN    :" + current_line
    elif line_type == LineType.RACE:
        print "RACE    :" + current_line
    elif line_type == LineType.VOTEFOR:
        print "VOTEFOR :" + current_line
    elif line_type == LineType.CANDIDATE:
        print "CAND    :" + current_line
    elif line_type == LineType.OTHER:
        print "OTHER   :" + current_line

def isVoteForLine(current_line):
    returnValue = False
    voteForMatch = re.match("^VOTE FOR ", current_line)
    if voteForMatch:
        returnValue = True
    return returnValue

def isTownLine(current_line):
    returnValue = False
    townMatch = re.match("^[0-9]{4}", current_line)
    if townMatch:
        returnValue = True
    return returnValue

def isRaceLine(current_line):
    returnValue = False
    raceMatch = re.match("^[A-Z]+", current_line)
    if raceMatch:
        if not current_line.startswith("DETAIL") and not current_line.startswith("RUN DATE"):
            returnValue = True
    return returnValue

def isCandidateLine(current_line):
    returnValue = False
    candidateMatch = re.match("\s[A-Z]+", current_line)
    if candidateMatch:
        if "- TOTAL" not in current_line:
            returnValue = True
    return returnValue

def determineLineType(current_line, previous_value):
    returnType = LineType.OTHER
    if isTownLine(current_line):
        returnType = LineType.TOWN
    elif isVoteForLine(current_line):
        returnType = LineType.VOTEFOR
    elif isRaceLine(current_line):
        returnType = LineType.RACE
    elif isCandidateLine(current_line):
        returnType = LineType.CANDIDATE
    return returnType

def stepThruData():
    print_data = False
    line_type = LineType.OTHER
    for line in open('../../openelections-sources-nj/2016/Sussex/GENERAL-EL30-OFFICIAL.html'):
        if "<pre>" in line:
            print_data = True
        if "</pre>" in line:
            print_data = False
        if print_data:
            line_type = determineLineType(line, line_type) 
            #printLine(line, line_type)

try:
    arg_parser = argparse.ArgumentParser(description='Parse New Jersey Sussex County data.')
    args = arg_parser.parse_args()

    validateArgs(args)

    stepThruData()

except Exception as e:
    print(e)
