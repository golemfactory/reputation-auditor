import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Set the aesthetic style of the plots
sns.set_style("whitegrid")

# Load the data
us_data = pd.read_csv('us_uptime.csv')
asia_data = pd.read_csv('asia_uptime.csv')
europe_data = pd.read_csv('europe_uptime.csv')

# Combine data for easier processing
us_data['region'] = 'US'
asia_data['region'] = 'Asia'
europe_data['region'] = 'Europe'
combined_data = pd.concat([us_data, asia_data, europe_data])

provider_ids = set(combined_data['provider_id'])

# Define thresholds
small_diff_threshold = 5  # Uptime difference threshold for 'roughly the same' (%)
large_diff_threshold = 15  # Uptime difference threshold for 'large difference' (%)

# Initialize counters for each zone
zone_counts = {'green': 0, 'yellow': 0, 'red': 0}

# Loop through each provider to categorize into zones
for provider_id in provider_ids:
    provider_data = combined_data[combined_data['provider_id'] == provider_id]
    
    if provider_data['region'].nunique() == 1:
        # Provider is only in one region
        continue  # Skip this provider as we're interested in differences across regions
    
    # Calculate max and min uptime for the provider
    max_uptime = provider_data['uptime_percentage'].max()
    min_uptime = provider_data['uptime_percentage'].min()
    diff = max_uptime - min_uptime

    # Categorize provider into zones
    if diff <= small_diff_threshold:
        zone_counts['green'] += 1
    elif diff <= large_diff_threshold:
        zone_counts['yellow'] += 1
    else:
        zone_counts['red'] += 1

# Plotting the count of providers in each zone
zones = list(zone_counts.keys())
counts = list(zone_counts.values())
sns.barplot(x=zones, y=counts, palette=zones)
plt.title('Count of Providers by Uptime Difference Zone')
plt.ylabel('Number of Providers')
plt.xlabel('Uptime Difference Zone')
plt.savefig('providers_by_uptime_zone.png')
plt.clf()

print("Aggregated plotting completed.")
