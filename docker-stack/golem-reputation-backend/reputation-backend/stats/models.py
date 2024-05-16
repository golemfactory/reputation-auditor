from django.db import models

class DailyProviderStats(models.Model):
    # Date for the statistics
    date = models.DateField(auto_now_add=True)
    
    # Success rate ratios
    success_rate_80_100 = models.FloatField(help_text="Ratio of providers with success rate between 80% and 100%")
    success_rate_50_80 = models.FloatField(help_text="Ratio of providers with success rate between 50% and 80%")
    success_rate_30_50 = models.FloatField(help_text="Ratio of providers with success rate between 30% and 50%")
    success_rate_0_30 = models.FloatField(help_text="Ratio of providers with success rate between 0% and 30%")
    
    # Uptime ratios
    uptime_80_100 = models.FloatField(help_text="Ratio of providers with uptime between 80% and 100%")
    uptime_50_80 = models.FloatField(help_text="Ratio of providers with uptime between 50% and 80%")
    uptime_30_50 = models.FloatField(help_text="Ratio of providers with uptime between 30% and 50%")
    uptime_0_30 = models.FloatField(help_text="Ratio of providers with uptime between 0% and 30%")
    
    # Total provider counts
    total_provider_count_mainnet = models.IntegerField(help_text="Total number of providers on Mainnet")
    total_provider_count_testnet = models.IntegerField(help_text="Total number of providers on Testnet")
    total_untested_provider = models.IntegerField(help_text="Total number of untested providers")
    total_tested_provider = models.IntegerField(help_text="Total number of tested providers")

    total_provider_rejected = models.IntegerField(help_text="Total number of rejected providers")
    total_provider_rejected_without_operator = models.IntegerField(help_text="Total number of rejected providers without operator", default=0)
    total_operator_rejected = models.IntegerField(help_text="Total number of operators rejected")

    class Meta:
        verbose_name = "Daily Provider Statistic"
        verbose_name_plural = "Daily Provider Statistics"
        indexes = [
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"Provider Stats for {self.date.strftime('%Y-%m-%d')}"
