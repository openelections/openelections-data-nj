import pandas as pd
import re
import os

def parse_election_results(excel_file, output_csv, county_name=None):
    """
    Parse New Jersey 2024 county-level election results from an Excel file
    and convert to standardized CSV format.
    
    Handles different formats for Morris, Middlesex, Mercer, and Monmouth Counties.
    
    Args:
        excel_file (str): Path to the Excel file containing election results
        output_csv (str): Path to save the output CSV file
        county_name (str): Name of the county (defaults to file name if not provided)
    """
    # Extract county name from filename if not provided
    if county_name is None:
        basename = os.path.basename(excel_file)
        county_match = re.search(r'(\w+)\s*County', basename, re.IGNORECASE)
        if county_match:
            county_name = county_match.group(1)
        else:
            county_name = "Unknown"
    
    # Load the Excel file
    print(f"Reading Excel file: {excel_file}")
    xl = pd.ExcelFile(excel_file)
    
    # Determine the file format type based on structure
    file_format = detect_file_format(xl)
    print(f"Detected file format: {file_format}")
    
    # Get the table of contents sheet to understand contests
    toc_df = pd.read_excel(xl, sheet_name="Table of Contents", header=3)
    toc_df = toc_df.dropna(how='all')
    
    # Extract contest names and their corresponding sheet numbers
    contests = {}
    for _, row in toc_df.iterrows():
        if pd.notna(row['Page']) and pd.notna(row['Contest']):
            page = int(row['Page'])
            contest = row['Contest']
            contests[page] = contest
    
    # Parse registered voters data
    reg_df = pd.read_excel(xl, sheet_name="Registered Voters")
    
    # Initialize results list to store all rows that will go into the final CSV
    results = []
    
    # Process registered voters and ballots cast data
    county = county_name
    
    # Determine columns structure for registered voters
    rv_cols = reg_df.columns.tolist()
    has_early_voting = 'Early Voting' in rv_cols
    has_mail_in = 'Mail-In Ballot' in rv_cols or 'Mail-in' in rv_cols
    has_election_day = 'Election Day' in rv_cols
    has_provisional = 'Provisional Ballot' in rv_cols or 'Provisional' in rv_cols
    has_emergency = 'Emergency' in rv_cols
    has_federal = 'Federal Ballots' in rv_cols or 'State/Fed' in rv_cols
    
    mail_col = next((c for c in rv_cols if 'Mail' in c), None)
    provisional_col = next((c for c in rv_cols if 'Provisional' in c), None)
    federal_col = next((c for c in rv_cols if 'Federal' in c or 'State/Fed' in c), None)
    
    # Add registered voters and ballots cast rows
    for _, row in reg_df.iterrows():
        # Determine which column has the precinct name based on format
        precinct_col = 'County' if file_format == 'monmouth' else 'Precinct'
        
        if precinct_col not in reg_df.columns:
            print(f"Warning: Cannot find {precinct_col} column in Registered Voters sheet")
            continue
            
        precinct = row[precinct_col]
        
        # Skip precinct if it's empty or contains "Total:"
        if pd.isna(precinct) or (isinstance(precinct, str) and "Total:" in precinct):
            continue
            
        # Add Registered Voters row
        registered_row = {
            'county': county,
            'precinct': precinct,
            'office': 'Registered Voters',
            'district': '',
            'candidate': '',
            'party': '',
            'early_voting': '',
            'election_day': '',
            'mail': '',
            'provisional': '',
            'emergency': '',
            'federal': '',
            'votes': int(row['Registered Voters'])
        }
        results.append(registered_row)
        
        # Add Ballots Cast row
        ballots_row = {
            'county': county,
            'precinct': precinct,
            'office': 'Ballots Cast',
            'district': '',
            'candidate': '',
            'party': '',
            'early_voting': int(row['Early Voting']) if has_early_voting and pd.notna(row.get('Early Voting', None)) else '',
            'election_day': int(row['Election Day']) if has_election_day and pd.notna(row.get('Election Day', None)) else '',
            'mail': int(row[mail_col]) if mail_col and pd.notna(row.get(mail_col, None)) else '',
            'provisional': int(row[provisional_col]) if provisional_col and pd.notna(row.get(provisional_col, None)) else '',
            'emergency': int(row['Emergency']) if has_emergency and pd.notna(row.get('Emergency', None)) else '',
            'federal': int(row[federal_col]) if federal_col and pd.notna(row.get(federal_col, None)) else '',
            'votes': int(row['Ballots Cast']) if 'Ballots Cast' in rv_cols else ''
        }
        results.append(ballots_row)
    
    # Process each contest sheet
    for page, contest_name in contests.items():
        if page == 1:  # Skip "Registered Voters" as it's already processed
            continue
            
        sheet_name = str(page)
        if sheet_name not in xl.sheet_names:
            print(f"Warning: Sheet {sheet_name} not found for contest: {contest_name}")
            continue
            
        print(f"Processing contest: {contest_name}")
        
        # Extract district information if present
        district = ''
        office = contest_name
        
        # Parse district information from contest name
        # Look for various district formats: CD 6, 7th Congressional District, etc.
        district_match = re.search(r'CD (\d+)', contest_name, re.IGNORECASE) or \
                         re.search(r'(\d+)(st|nd|rd|th)', contest_name, re.IGNORECASE) or \
                         re.search(r'District (\d+)', contest_name, re.IGNORECASE)
        if district_match:
            district = district_match.group(1)  # Extract just the number
            
        # Clean up office name to remove the "Vote For X" part and trim
        office = re.sub(r'\(Vote For \d+\)', '', office).strip()
        
        # Process each contest sheet based on the detected format
        if file_format == 'mercer':
            process_mercer_format(xl, sheet_name, office, district, county, results)
        elif file_format == 'monmouth':
            process_monmouth_format(xl, sheet_name, office, district, county, results)
        else:  # Morris or Middlesex format
            process_morris_format(xl, sheet_name, office, district, county, results)
    
    # Convert results to DataFrame and save to CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_csv, index=False)
    print(f"Saved results to {output_csv}")
    print(f"Total rows: {len(results_df)}")


def detect_file_format(xl):
    """
    Detect the file format by examining the structure of the sheets.
    
    Args:
        xl (pd.ExcelFile): The Excel file to analyze
        
    Returns:
        str: 'morris', 'mercer', 'middlesex', or 'monmouth'
    """
    # Check registered voters sheet
    reg_df = pd.read_excel(xl, sheet_name="Registered Voters")
    
    # Check headers
    headers = reg_df.columns.tolist()
    
    # Monmouth format has just County, Registered Voters, Ballots Cast columns
    # And "County" as column 0 instead of "Precinct"
    if headers and headers[0] == 'County' and len(headers) <= 4:
        return 'monmouth'
    
    # Mercer format has 'Vote by Mail' column
    if any('Vote by Mail' in col for col in headers):
        return 'mercer'
    
    # Middlesex format has 'Mail-In Ballot' column 
    if any('Mail-In Ballot' in col for col in headers):
        return 'middlesex'
    
    # Otherwise assume Morris format
    return 'morris'


def process_morris_format(xl, sheet_name, office, district, county, results):
    """
    Process a contest sheet in Morris/Middlesex County format.
    
    Args:
        xl (pd.ExcelFile): The Excel file
        sheet_name (str): The sheet name to process
        office (str): The office name
        district (str): The district number (if any)
        county (str): The county name
        results (list): List to append results to
    """
    # Read the contest sheet
    contest_df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
    
    # Find the row with precinct names (typically row 2)
    header_row = None
    for i in range(len(contest_df)):
        if isinstance(contest_df.iloc[i, 0], str) and contest_df.iloc[i, 0] == 'Precinct':
            header_row = i
            break
    
    if header_row is None:
        print(f"Warning: Could not find 'Precinct' row in sheet {sheet_name}")
        return
    
    # Extract candidates row (one above header)
    candidates_row = contest_df.iloc[header_row-1]
    
    # Get all column names from header row
    headers = contest_df.iloc[header_row]
    
    # Get the column indices for each candidate by aligning with header row
    candidate_data = {}
    current_candidate = None
    
    for col_idx, value in enumerate(candidates_row):
        if pd.notna(value) and value not in ['', 'Precinct', 'Registered Voters']:
            # This is a candidate name, start a new group
            current_candidate = value
            candidate_data[current_candidate] = {'columns': []}
            
        if current_candidate is not None:
            col_header = headers[col_idx]
            if pd.notna(col_header) and col_header not in ['Precinct', 'Registered Voters']:
                candidate_data[current_candidate]['columns'].append({'index': col_idx, 'type': col_header})
    
    # Process vote data starting from the row after the header
    data_start = header_row + 1
    
    for row_idx in range(data_start, len(contest_df)):
        row = contest_df.iloc[row_idx]
        precinct = row[0]
        
        # Skip rows where precinct is empty or contains "Total:"
        if pd.isna(precinct) or precinct == '' or (isinstance(precinct, str) and "Total:" in precinct):
            continue
        
        # Process each candidate's votes
        for candidate, data in candidate_data.items():
            early_voting = 0
            election_day = 0
            mail_in = 0
            provisional = 0
            emergency = 0
            federal = 0
            
            # Extract vote counts from columns
            for col in data['columns']:
                col_idx = col['index']
                col_type = col['type']
                
                if col_idx >= len(row) or pd.isna(row[col_idx]):
                    continue
                
                value = row[col_idx]
                if not pd.isna(value) and value != '':
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        # Skip non-integer values
                        continue
                        
                    # Assign to appropriate vote type
                    if col_type == 'Early Voting':
                        early_voting += value
                    elif col_type == 'Election Day':
                        election_day += value
                    elif 'Mail' in col_type:
                        mail_in += value
                    elif 'Provisional' in col_type:
                        provisional += value
                    elif col_type == 'Emergency':
                        emergency += value
                    elif col_type in ['State/Fed', 'Federal Ballots']:
                        federal += value
            
            # Calculate total votes
            total_votes = early_voting + election_day + mail_in + provisional + emergency + federal
            
            # Skip if no votes (all zeros)
            if total_votes == 0:
                continue
            
            # Create result row
            result_row = {
                'county': county,
                'precinct': precinct,
                'office': office,
                'district': district,
                'candidate': candidate,
                'party': '',  # Party information not provided in the sheets
                'early_voting': early_voting,
                'election_day': election_day,
                'mail': mail_in,
                'provisional': provisional,
                'emergency': emergency,
                'federal': federal,
                'votes': total_votes
            }
            results.append(result_row)


def process_mercer_format(xl, sheet_name, office, district, county, results):
    """
    Process a contest sheet in Mercer County format.
    
    Args:
        xl (pd.ExcelFile): The Excel file
        sheet_name (str): The sheet name to process
        office (str): The office name
        district (str): The district number (if any)
        county (str): The county name
        results (list): List to append results to
    """
    # Read the contest sheet
    contest_df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
    
    # Find the row with precinct names (typically row 2)
    header_row = None
    for i in range(len(contest_df)):
        if isinstance(contest_df.iloc[i, 0], str) and contest_df.iloc[i, 0] == 'Precinct':
            header_row = i
            break
    
    if header_row is None:
        print(f"Warning: Could not find 'Precinct' row in sheet {sheet_name}")
        return
    
    # Extract candidates row (one above header)
    candidates_row = contest_df.iloc[header_row-1]
    
    # Get all column names from header row
    headers = contest_df.iloc[header_row]
    
    # Get the candidates and their column ranges
    candidates = []
    for col_idx, value in enumerate(candidates_row):
        if pd.notna(value) and value != '' and value not in ['Precinct', 'Registered Voters']:
            candidates.append({
                'name': value,
                'start_col': col_idx
            })
    
    # Set the end column for each candidate
    for i in range(len(candidates) - 1):
        candidates[i]['end_col'] = candidates[i+1]['start_col']
    
    # Set the end column for the last candidate
    if len(candidates) > 0:
        candidates[-1]['end_col'] = len(headers)
    
    # Process vote data starting from the row after the header
    data_start = header_row + 1
    
    for row_idx in range(data_start, len(contest_df)):
        row = contest_df.iloc[row_idx]
        precinct = row[0]
        
        # Skip rows where precinct is empty or contains "Total:"
        if pd.isna(precinct) or precinct == '' or (isinstance(precinct, str) and "Total:" in precinct):
            continue
        
        # Process each candidate's votes
        for candidate_data in candidates:
            candidate = candidate_data['name']
            start_col = candidate_data['start_col']
            end_col = candidate_data['end_col']
            
            # Find vote type columns for this candidate
            early_voting = None
            vote_by_mail = None
            provisional = None
            election_day = None
            federal = None
            total_votes = None
            
            # Locate the column indices for each vote type
            for col_idx in range(start_col, end_col):
                if col_idx >= len(headers):
                    continue
                    
                col_name = headers[col_idx]
                if pd.isna(col_name):
                    continue
                    
                if col_name == 'Early Voting':
                    early_voting = row[col_idx]
                elif col_name == 'Vote by Mail':
                    vote_by_mail = row[col_idx]
                elif col_name == 'Provisional':
                    provisional = row[col_idx]
                elif col_name == 'Election Day':
                    election_day = row[col_idx]
                elif col_name == 'Federal Ballots':
                    federal = row[col_idx]
                elif col_name == 'Total Votes':
                    total_votes = row[col_idx]
            
            # Handle protected values and convert to integers
            try:
                early_value = early_voting
                if early_voting != 'protected':
                    early_value = int(early_voting) if pd.notna(early_voting) and early_voting != '' else 0
                    
                mail_value = int(vote_by_mail) if pd.notna(vote_by_mail) and vote_by_mail != '' else 0
                prov_value = int(provisional) if pd.notna(provisional) and provisional != '' else 0
                eday_value = int(election_day) if pd.notna(election_day) and election_day != '' else 0
                fed_value = int(federal) if pd.notna(federal) and federal != '' else 0
                
                # Get total votes from the Total Votes column if available, otherwise calculate
                if pd.notna(total_votes) and total_votes != '':
                    total = int(total_votes)
                else:
                    # Only include early_value in sum if it's a number
                    if early_voting != 'protected':
                        total = early_value + mail_value + prov_value + eday_value + fed_value
                    else:
                        # If early voting is protected, sum the others
                        total = mail_value + prov_value + eday_value + fed_value
            except (ValueError, TypeError) as e:
                # Skip if can't convert values
                print(f"Warning: Could not parse vote counts for {candidate} in {precinct}")
                print(f"  - Values: early={early_voting}, vbm={vote_by_mail}, prov={provisional}, eday={election_day}, fed={federal}, total={total_votes}")
                print(f"  - Error: {str(e)}")
                continue
            
            # Skip if no votes
            if (early_voting != 'protected' and (mail_value + prov_value + eday_value + fed_value + early_value) == 0) or \
               (early_voting == 'protected' and (mail_value + prov_value + eday_value + fed_value) == 0 and total_votes == 0):
                continue
            
            # Create result row
            result_row = {
                'county': county,
                'precinct': precinct,
                'office': office,
                'district': district,
                'candidate': candidate,
                'party': '',  # Party information not provided in the sheets
                'early_voting': early_value,
                'election_day': eday_value,
                'mail': mail_value,
                'provisional': prov_value,
                'emergency': 0,  # Mercer doesn't use emergency column
                'federal': fed_value,
                'votes': total
            }
            results.append(result_row)


def process_monmouth_format(xl, sheet_name, office, district, county, results):
    """
    Process a contest sheet in Monmouth County format.
    
    Args:
        xl (pd.ExcelFile): The Excel file
        sheet_name (str): The sheet name to process
        office (str): The office name
        district (str): The district number (if any)
        county (str): The county name
        results (list): List to append results to
    """
    # Read the contest sheet
    contest_df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
    
    # Find the row with county/precinct names (typically row 2)
    header_row = None
    for i in range(len(contest_df)):
        if isinstance(contest_df.iloc[i, 0], str) and contest_df.iloc[i, 0] == 'County':
            header_row = i
            break
    
    if header_row is None:
        print(f"Warning: Could not find 'County' row in sheet {sheet_name}")
        return
    
    # Extract candidates row (one above header)
    candidates_row = contest_df.iloc[header_row-1]
    
    # Get all column names from header row
    headers = contest_df.iloc[header_row]
    
    # Get the column indices for each candidate
    candidate_cols = {}
    current_candidate = None
    
    for col_idx, value in enumerate(candidates_row):
        if pd.notna(value) and value != '' and value not in ['County', 'Registered Voters', '']:
            # This is a candidate name, save the column index
            candidate_cols[value] = col_idx
    
    # Process vote data starting from the row after the header
    data_start = header_row + 1
    
    for row_idx in range(data_start, len(contest_df)):
        row = contest_df.iloc[row_idx]
        precinct = row[0]
        
        # Skip rows where precinct is empty or contains "Total:"
        if pd.isna(precinct) or precinct == '' or (isinstance(precinct, str) and "Total:" in precinct):
            continue
        
        # Process each candidate's votes
        for candidate, col_idx in candidate_cols.items():
            if col_idx >= len(row):
                continue
                
            # Get total votes
            total_votes = row[col_idx]
            
            # Skip if no votes or invalid value
            if pd.isna(total_votes) or total_votes == '':
                continue
                
            try:
                total_votes = int(total_votes)
                
                # Skip if no votes
                if total_votes == 0:
                    continue
                    
                # Create result row
                result_row = {
                    'county': county,
                    'precinct': precinct,
                    'office': office,
                    'district': district,
                    'candidate': candidate,
                    'party': '',  # Party information not provided in the sheets
                    'early_voting': '',  # Monmouth doesn't break down by vote type
                    'election_day': '',
                    'mail': '',
                    'provisional': '',
                    'emergency': '',
                    'federal': '',
                    'votes': total_votes
                }
                results.append(result_row)
            except (ValueError, TypeError):
                print(f"Warning: Could not convert vote count for {candidate} in {precinct}")
                continue


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Parse NJ 2024 county election results")
    parser.add_argument("input_file", help="Path to the Excel file with election results")
    parser.add_argument("--output", "-o", help="Path to save the output CSV file", default=None)
    parser.add_argument("--county", "-c", help="County name (if not in filename)", default=None)
    
    args = parser.parse_args()
    
    # Generate output filename if not provided
    if args.output is None:
        basename = os.path.splitext(os.path.basename(args.input_file))[0]
        args.output = f"{basename}_parsed.csv"
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        exit(1)
    
    parse_election_results(args.input_file, args.output, args.county)