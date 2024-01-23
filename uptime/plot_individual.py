import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from os.path import join

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

# Get unique provider IDs
provider_ids = set(combined_data['provider_id'])

# Define thresholds
small_diff_threshold = 5  # Uptime difference threshold for 'roughly the same' (%)
large_diff_threshold = 15  # Uptime difference threshold for 'large difference' (%)

# Loop through each provider
for provider_id in provider_ids:
    provider_data = combined_data[combined_data['provider_id'] == provider_id]
    
    if provider_data['region'].nunique() == 1:
        # Provider is only in one region
        print(f"Provider {provider_id} is only in {provider_data['region'].iloc[0]}!!!")
    else:
        # Calculate max and min uptime for the provider
        max_uptime = provider_data['uptime_percentage'].max()
        min_uptime = provider_data['uptime_percentage'].min()
        diff = max_uptime - min_uptime

        # Determine bar color based on uptime difference
        if diff <= small_diff_threshold:
            bar_color = 'green'
        elif diff <= large_diff_threshold:
            bar_color = 'yellow'
        else:
            bar_color = 'red'

        # Plotting
        sns.barplot(x='region', y='uptime_percentage', data=provider_data, color=bar_color)
        plt.title(f"{provider_id} - Uptime Difference: {diff:.2f}%")
        plt.ylabel('Uptime Percentage')
        plt.xlabel('Region')
        
        # Save the plot
        plt.savefig(f"provider_{provider_id}_uptime.png")
        plt.clf()

print("Plotting completed.")
