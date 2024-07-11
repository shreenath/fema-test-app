import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import io

# Streamlit configuration for external access
st.set_page_config(page_title="FEMA Disaster Declarations for Community Organizers", layout="wide")

# Census API key
CENSUS_API_KEY = "0522c0d0532fd5a530a4cb82419a270033894e74"

# URL for the 2019 Gazetteer Files
GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2019_Gazetteer/2019_Gaz_zcta_national.zip"

# Dictionary of state abbreviations to FIPS codes
STATE_FIPS = {
    'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06', 'CO': '08', 'CT': '09', 'DE': '10', 'FL': '12', 'GA': '13',
    'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19', 'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24',
    'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28', 'MO': '29', 'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 'NJ': '34',
    'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39', 'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45',
    'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50', 'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55', 'WY': '56',
    'AS': '60', 'GU': '66', 'MP': '69', 'PR': '72', 'VI': '78'
}

@st.cache_data(ttl=3600)
def get_fema_disasters(last_month=True):
    url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
    one_month_ago = datetime.now() - timedelta(days=30)
    params = {
        "$filter": f"declarationDate ge '{one_month_ago.strftime('%Y-%m-%dT%H:%M:%S.000z')}'",
        "$orderby": "declarationDate desc",
        "$top": 1000,
        "$format": "json"
    }
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('DisasterDeclarationsSummaries', [])
        
        return records
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error: Unable to fetch FEMA data. {str(e)}")
        return None

@st.cache_data(ttl=3600)
def get_gazetteer_data():
    try:
        response = requests.get(GAZETTEER_URL)
        response.raise_for_status()
        
        zip_file = io.BytesIO(response.content)
        df = pd.read_csv(zip_file, compression='zip', sep='\t', dtype={'GEOID': str})
        df['STATE'] = df['GEOID'].str[:2]
        df['COUNTY'] = df['GEOID'].str[2:5]
        
        return df
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error: Unable to fetch Gazetteer data. {str(e)}")
        return None

def get_county_zip_mapping(state, county, gazetteer_data):
    state_fips = STATE_FIPS.get(state)
    if not state_fips:
        return []
    
    county_data = gazetteer_data[(gazetteer_data['STATE'] == state_fips) & (gazetteer_data['COUNTY'] == county)]
    
    if county_data.empty:
        return []
    
    return county_data['GEOID'].tolist()

def process_disasters(disasters, gazetteer_data):
    if not disasters:
        return pd.DataFrame()
    
    processed_data = []
    
    for disaster in disasters:
        disaster_number = disaster.get('disasterNumber')
        declaration_date = disaster.get('declarationDate')
        incident_type = disaster.get('incidentType')
        state = disaster.get('state')
        designated_area = disaster.get('designatedArea', '')
        
        # Use the provided disaster name or construct one if not available
        disaster_name = disaster.get('declarationTitle')
        if not disaster_name:
            disaster_name = f"{state} {incident_type} (DR-{disaster_number})"
        
        county = designated_area.split('(')[0].strip() if isinstance(designated_area, str) else ''
        
        ia_program = 'Yes' if disaster.get('iaProgramDeclared') else 'No'
        ih_program = 'Yes' if disaster.get('ihProgramDeclared') else 'No'
        pa_program = 'Yes' if disaster.get('paProgramDeclared') else 'No'
        hm_program = 'Yes' if disaster.get('hmProgramDeclared') else 'No'
        
        eligibility = []
        if ia_program == 'Yes':
            eligibility.append('Individual Assistance')
        if ih_program == 'Yes':
            eligibility.append('Individual and Households Program')
        if pa_program == 'Yes':
            eligibility.append('Public Assistance')
        if hm_program == 'Yes':
            eligibility.append('Hazard Mitigation')
        eligibility = ', '.join(eligibility) if eligibility else 'None'
        
        zip_codes = get_county_zip_mapping(state, county, gazetteer_data)
        
        processed_data.append({
            'Disaster Number': disaster_number,
            'Disaster Name': disaster_name,
            'Declaration Date': declaration_date,
            'Incident Type': incident_type,
            'State': state,
            'County': county,
            'Eligibility': eligibility,
            'Individual Assistance': ia_program,
            'Individual and Households Program': ih_program,
            'Public Assistance': pa_program,
            'Hazard Mitigation': hm_program,
            'Zip Codes': ', '.join(zip_codes) if zip_codes else 'Not available'
        })
    
    df = pd.DataFrame(processed_data)
    df['Declaration Date'] = pd.to_datetime(df['Declaration Date']).dt.strftime('%Y-%m-%d')
    
    return df

def main():
    st.title("FEMA Disaster Declarations for Community Organizers")
    st.write("This app displays recent FEMA disaster declarations and allows community organizers to access relevant information.")

    with st.spinner("Fetching and processing disaster data..."):
        disasters = get_fema_disasters()
        gazetteer_data = get_gazetteer_data()
        if disasters and gazetteer_data is not None:
            df = process_disasters(disasters, gazetteer_data)
        else:
            df = pd.DataFrame()
    
    if not df.empty:
        st.success(f"Total number of disaster declarations: {len(df)}")
        
        # Create two columns for state and disaster selection
        col1, col2 = st.columns(2)
        
        with col1:
            # Create a selectbox for states
            states = sorted(df['State'].unique())
            selected_state = st.selectbox("Select a State:", states)
        
        if selected_state:
            state_disasters = df[df['State'] == selected_state]
            
            with col2:
                # Create a selectbox for disasters in the selected state
                disaster_options = sorted(state_disasters['Disaster Name'].unique())
                selected_disaster = st.selectbox("Select a disaster:", disaster_options)
            
            if selected_disaster:
                disaster_data = df[(df['State'] == selected_state) & (df['Disaster Name'] == selected_disaster)]
                
                if disaster_data.empty:
                    st.warning(f"No data found for {selected_disaster} in {selected_state}. This may be due to data updates or changes in the FEMA database.")
                else:
                    st.subheader(f"{selected_disaster}")
                    st.write(f"**Declaration Date:** {disaster_data['Declaration Date'].iloc[0]}")
                    st.write(f"**Incident Type:** {disaster_data['Incident Type'].iloc[0]}")
                    
                    st.subheader("Affected Areas and Zip Codes")
                    for _, row in disaster_data.iterrows():
                        with st.expander(f"{row['County']}, {row['State']}"):
                            st.write(f"**Eligibility:** {row['Eligibility']}")
                            st.write(f"**Individual Assistance:** {row['Individual Assistance']}")
                            st.write(f"**Individual and Households Program:** {row['Individual and Households Program']}")
                            st.write(f"**Public Assistance:** {row['Public Assistance']}")
                            st.write(f"**Hazard Mitigation:** {row['Hazard Mitigation']}")
                            if row['Zip Codes'] != 'Not available':
                                st.write(f"**Zip Codes:** {row['Zip Codes']}")
                            else:
                                st.write("**Zip Codes:** Not available")
                    
                    st.subheader("Filter Options")
                    selected_counties = st.multiselect("Filter by County:", disaster_data['County'].unique())
                    selected_eligibility = st.multiselect("Filter by Eligibility:", disaster_data['Eligibility'].unique())
                    
                    filtered_data = disaster_data
                    if selected_counties:
                        filtered_data = filtered_data[filtered_data['County'].isin(selected_counties)]
                    if selected_eligibility:
                        filtered_data = filtered_data[filtered_data['Eligibility'].isin(selected_eligibility)]
                    
                    st.subheader("Filtered Data")
                    st.dataframe(filtered_data)
                    
                    csv = filtered_data.to_csv(index=False)
                    st.download_button(
                        label="Download filtered data as CSV",
                        data=csv,
                        file_name=f"{selected_disaster.replace(' ', '_')}_data.csv",
                        mime="text/csv",
                    )
        
    else:
        st.warning("No disaster data available for the specified period.")

    # Add debugging information
    if st.checkbox("Show debugging information"):
        st.subheader("Debugging Information")
        st.write("Raw FEMA API Response:")
        st.json(disasters)
        st.write("Processed DataFrame:")
        st.dataframe(df)

if __name__ == "__main__":
    main()