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
import json
import csv

arg_parser = argparse.ArgumentParser(description='Parse New Jersey Count data.')
arg_parser.add_argument('configfile', type=str, nargs=1) 
arg_parser.add_argument('--muni', help='run in municipality mode', action='store_true')
args = arg_parser.parse_args()

def validateArgs( p_args ):
    if args.muni:
        print ' ***** Running in Municipality Mode *****'
    if os.path.isfile(args.configfile[0]) != True:
        sys.exit('ERROR: Config File ' + args.configfile[0] + ' does not exist')
    else:
        print ' Using config file ' + args.configfile[0]
    return

def readJsonConfig ( p_args ):
    with open(p_args.configfile[0]) as config_file:
        config_data = json.load(config_file)
    return config_data

def openOutputFile( p_config ):
    full_output_file = os.path.join(p_config['output_directory'], p_config['output_file'])
    try:
        f = open( full_output_file, 'w') 
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    except:
        sys.exit('ERROR: Could not open output file: ' + full_output_file)
    return writer

def print_header( p_outfile):
    if args.muni:
        p_outfile.writerow( ('county','municipality','office','district','party','candidate','votes') )
    else:
        p_outfile.writerow( ('county','office','district','party','candidate','votes') )
    return

def doesJsonKeyExist( p_config, p_key ):
    key_exists = True
    if p_key not in p_config:
        key_exists = False
    return key_exists

def get_county_name(p_infile):
    return

def clean_text_values(p_text):
    if p_text.strip() == "":
        clean_text = "0"
    else:
        clean_text = p_text.replace(',', '').strip()
    return clean_text

def clean_vote_values(p_text):
    clean_text = p_text.replace('', '')
    if p_text.strip() == "":
        clean_text = "0"
    else:
        clean_text = p_text.strip()
    return clean_text

def populate_candidate_party_lists( p_candidateList, p_partyList, p_header):
    counter = 0
    value0 = ""
    value1 = ""
    for value in p_header.split('\r'):
        if counter == 0:
            value0 = value
        elif counter == 1:
            value1 = value
        counter = counter + 1
    if counter > 1:
        p_candidateList.append(value0)
        p_partyList.append(value1)
    return

def print_county_totals( p_candidateList, p_partyList, p_line, p_outfile, p_config):
    valid_column = p_config['columns'].split(",")
    for i in range(len(p_line)):
        print_value=False
        if i > 0:
            if p_config['columns'] == '*':
                print_value=True
            else:   
                if str(i) in valid_column:
                    print_value=True
        if print_value == True:
            p_outfile.writerow((p_config['county'], 
                                p_config['office'],
                                p_config['district'],
                                p_partyList[i-1], 
                                p_candidateList[i-1], 
                                clean_text_values(p_line[i]) 
                               ))
    return

def print_muni_totals( p_candidateList, p_partyList, p_line, p_outfile, p_config):
    valid_column = p_config['columns'].split(",")
    for i in range(len(p_line)):
        print_value=False
        if i > 0:
            if p_config['columns'] == '*':
                print_value=True
            else:   
                if str(i) in valid_column:
                    print_value=True
        if print_value == True:
            p_outfile.writerow((p_config['county'], 
                                p_line[0],
                                p_config['office'],
                                p_config['district'],
                                p_partyList[i-1], 
                                p_candidateList[i-1], 
                                clean_text_values(p_line[i]) 
                               ))
    return

def process_header_line( p_candidateList, p_partyList, p_line, p_config):
    for header in p_line:
        populate_candidate_party_lists(p_candidateList, p_partyList, header)
    return

def process_data_line( p_candidateList, p_partyList, p_line, p_outfile, p_config):
    if args.muni:
        if "TOTAL" not in p_line[0].upper():
            print_muni_totals(p_candidateList, p_partyList, p_line, p_outfile, p_config)
    else:
        if "TOTAL" in p_line[0].upper():
            print_county_totals(p_candidateList, p_partyList, p_line, p_outfile, p_config)
    return

def process_single_file(p_config, p_outfile, p_infile):
    counter = 0
    candidateList = []
    partyList = []
    if os.path.isfile(p_infile) != True:
        print 'ERROR: Input File ' + p_infile + ' does not exist'
    else:
        with open(p_infile, 'rb') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            for line in csvreader:
                counter = counter + 1
                if counter == 1:
                    process_header_line(candidateList, partyList, line, p_config)
                else:
                    process_data_line(candidateList, partyList, line, p_outfile, p_config)
    return

def process_input_files(p_config, p_outfile, p_config_key):
    input_path = p_config[p_config_key]['input_directory']
    race_data = p_config[p_config_key]
    for input_file in race_data['input_files']:
        full_input_file = os.path.join(input_path, input_file["file"])
        process_single_file(input_file, p_outfile, full_input_file)
    return

def process_single_race( p_config, p_outfile, p_config_key):
    if doesJsonKeyExist(p_config, p_config_key):
        print ' Found data for ' + p_config_key + '. Processing this race.'
        process_input_files(p_config, p_outfile, p_config_key)
    else:
        print ' Config file doesn\'t contain data for ' + p_config_key + '. Skipping this race.'
    return

def process_config_data(p_config, p_outfile):
    print_header(p_outfile)
    process_single_race(p_config, p_outfile, 'president')
    process_single_race(p_config, p_outfile, 'us_house')
    process_single_race(p_config, p_outfile, 'us_senate')
    process_single_race(p_config, p_outfile, 'nj_senate')
    process_single_race(p_config, p_outfile, 'nj_assembly')
    return

validateArgs( args )
config = readJsonConfig( args )
out_file = openOutputFile(config)
try:
    process_config_data(config, out_file)
except:
    print sys.exc_info()[0]

