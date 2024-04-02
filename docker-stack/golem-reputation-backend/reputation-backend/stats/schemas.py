from typing import List, Optional
from ninja import Schema

class OfferHistorySchema(Schema):
    task_name: str
    offered_at: str
    offer_status: str
    reason_for_rejection: Optional[str] = None

class TaskParticipationSchema(Schema):
    task_id: int
    completion_status: str
    error_message: Optional[str] = None
    cost: Optional[float] = None



class ProviderDetailsResponseSchema(Schema):
    offer_history: List[OfferHistorySchema]
    task_participation: List[TaskParticipationSchema]