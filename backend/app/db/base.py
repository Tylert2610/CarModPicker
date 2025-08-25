# Import all the models, so that Base has them before being
# imported by Alembic
from app.api.models.build_list import BuildList
from app.api.models.build_list_part import BuildListPart
from app.api.models.car import Car
from app.api.models.category import Category
from app.api.models.global_part import GlobalPart
from app.api.models.global_part_report import GlobalPartReport
from app.api.models.global_part_vote import GlobalPartVote
from app.api.models.subscription import Subscription

# actual models
from app.api.models.user import User
from app.db.base_class import Base
