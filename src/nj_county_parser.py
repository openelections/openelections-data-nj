#!/usr/bin/python

import sys
import argparse
import os.path
import json

arg_parser = argparse.ArgumentParser(description='Parse New Jersey Count data.')
arg_parser.add_argument('configfile', type=str, nargs=1)
args = arg_parser.parse_args()

def validateArgs( p_args ):
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
    except:
        sys.exit('ERROR: Could not open output file: ' + full_output_file)
    return f

def process_config_data(p_config, p_outfile):
    print 'processing!'
    return

validateArgs( args )
config = readJsonConfig( args )
out_file = openOutputFile(config)
try:
    process_config_data(config, out_file)
except:
    print 'ERROR:' + sys.exc_info()[0]
    out_file.close()

