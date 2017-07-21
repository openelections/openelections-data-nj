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
import xml.etree.ElementTree

class ContestConfig (object):

    def __init__ (self, xmlKey, office, district):
        self.xmlKey = xmlKey
        self.office = office
        self.district = district
        self.party = ''
        self.precinct = ''
        self.candidate = ''
        self.votes = 0

    def parsePartyCandidateLine(self, textValue):
        if (textValue != 'Write-In'):
            newValues = textValue.split('-')
            self.party = newValues[0].strip()
            self.candidate = newValues[1].strip()
        else:
            self.party = ''
            self.candidate = textValue
        return

    def printCSVLine(self, outFile):
        outFile.writerow( ('Morris', self.precinct, self.office, self.district, self.candidate, self.party, self.votes) )
        return

def openOutputFile(outputPath):
    try:
        f = open( outputPath, 'w') 
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    except:
        sys.exit('ERROR: Could not open output file: ' + outputPath)
    return writer

def processPrecinct(xmlNode, xmlConfig, outFile):
    #print ('            ' + xmlNode.get('name'))
    xmlConfig.precinct = xmlNode.get('name')
    xmlConfig.votes = xmlNode.get('votes')
    xmlConfig.printCSVLine(outFile)
    return

def processVoteType(xmlNode, xmlConfig, outFile):
    #print ('         ' + xmlNode.get('name'))
    if (xmlNode.get('name') == 'Election'):
        for objPrecinct in xmlNode.findall('Precinct'):
            processPrecinct(objPrecinct, xmlConfig, outFile)
    return

def processChoice(xmlNode, xmlConfig, outFile):
    #print ('    ' + xmlNode.get('text'))
    xmlConfig.parsePartyCandidateLine(xmlNode.get('text'))
    for objVoteType in xmlNode.findall('VoteType'):
        processVoteType(objVoteType, xmlConfig, outFile)
    return

def processSingleContest(xmlRoot, xmlConfig, outFile):
    xmlNode = findContestByName(xmlRoot, xmlConfig.xmlKey)
    #print (xmlNode.get('text'))
    for objChoice in xmlNode.findall('Choice'):
        processChoice(objChoice, xmlConfig, outFile)
    return

def findContestByName(xmlNode, contestName):
    return_value = None
    for objContest in xmlNode.findall('Contest'):
        if (objContest.get('text') == contestName):
            return_value = objContest
            break
    return return_value

def processXmlFile(in_file, out_file):

    xmlRoot = xml.etree.ElementTree.parse(in_file).getroot()
    outFile = openOutputFile(out_file)
    outFile.writerow( ('county', 'precinct', 'office', 'district', 'candidate', 'party', 'votes') )

    objConfig = ContestConfig('President', 'President', None)
    processSingleContest(xmlRoot, objConfig, outFile)

    objConfig = ContestConfig('House of Representatives 7th Congressional', 'U.S. House', '7')
    processSingleContest(xmlRoot, objConfig, outFile)

    objConfig = ContestConfig('House of Representatives 11th Congressional', 'U.S. House', '11')
    processSingleContest(xmlRoot, objConfig, outFile)

    return

try:
    processXmlFile('../../openelections-sources-nj/2016/Morris/general.xml', '../2016/20161108__nj__general__morris__precinct.csv')
except Exception as e:
    print(e)
