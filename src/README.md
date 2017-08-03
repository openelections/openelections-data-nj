# nj\_county\_parser.py

This script was used to parse 2016 and 2014 data.  The input files downloaded from the state and extracted via Tabula required too much manual editing prior to processing, so the script was abandoned and nj\_gen\_elec\_parser.py was created take its place.  Unless you are are re-processing 2014 or 2016 county or municipal data, it is suggested to use nj\_gen\_elec\_parser.py.

To run the script, you first have to create a JSON configuration file.  This file tells the script all the input files and output files to use and the various parameters to use with each file.  You would then supply the JSON file as the only required input parameter to the script.  To run the script to process data and produce a file with county-level data:

```
$ python nj_county_parser.py nj_20141104_general.json
```

You can also run this script to produce a file with municipality-level data with the --muni parameter:

```
$ python nj_county_parser.py nj_20141104_general.json --muni
```

# nj\_gen\_elec\_parser.py

This script function very similarly to nj\_couty\_parser.py, only there is less pre-editing required when preparing the input files.  The same general format is used in both the JSON config files and the --muni parameter.  This script is used for all years except for 2014 and 2016.
