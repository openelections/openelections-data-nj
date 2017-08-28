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

def openFileIntoString(fileName):
    myFile = open(fileName, 'r')
    myText = myFile.read()
    myFile.close()
    return myText

def getElectionData():
    data = openFileIntoString('../../openelections-sources-nj/2016/Sussex/GENERAL-EL30-OFFICIAL.html')
    root = PARSER.fromstring(data)
    electionData = ''
    for els in root.getiterator():
        if els.tag == 'pre':
            print 'Found the pre tag'
            electionData = els.text_content()
    return electionData

try:
    arg_parser = argparse.ArgumentParser(description='Parse New Jersey Sussex County data.')
    args = arg_parser.parse_args()

    validateArgs(args)

    myData = getElectionData()

except Exception as e:
    print(e)
