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

# Average Uptime by Region
avg_uptime_by_region = combined_data.groupby('region')['uptime_percentage'].mean()
sns.barplot(x=avg_uptime_by_region.index, y=avg_uptime_by_region.values)
plt.title('Average Uptime by Region')
plt.ylabel('Average Uptime Percentage')
plt.xlabel('Region')
plt.savefig('average_uptime_by_region.png')
plt.clf()

# Distribution of Uptime Percentages
sns.boxplot(x='region', y='uptime_percentage', data=combined_data)
plt.title('Distribution of Uptime Percentages by Region')
plt.ylabel('Uptime Percentage')
plt.xlabel('Region')
plt.savefig('uptime_distribution_by_region.png')
plt.clf()

# Uptime Consistency (Standard Deviation)
std_dev_uptime_by_region = combined_data.groupby('region')['uptime_percentage'].std()
sns.barplot(x=std_dev_uptime_by_region.index, y=std_dev_uptime_by_region.values)
plt.title('Uptime Consistency by Region (Standard Deviation)')
plt.ylabel('Standard Deviation of Uptime Percentage')
plt.xlabel('Region')
plt.savefig('uptime_consistency_by_region.png')
plt.clf()

print("Aggregated plotting completed.")
