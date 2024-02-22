from ninja import NinjaAPI, Path
from django.http import JsonResponse
import json
api = NinjaAPI(
    title="Golem Reputation API",
    version="2.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api2",
)
import redis



r = redis.Redis(host='redis', port=6379, db=0)


@api.get("/providers/scores")
def list_provider_scores(request):
    response = r.get('provider_scores_v2')

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available in Redis
        return JsonResponse({"error": "Data not available"}, status=503)


