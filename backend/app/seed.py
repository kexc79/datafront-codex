from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Role, User
from app.oracle import seed_dictionary_queries
from app.security import get_password_hash


def bootstrap(db: Session) -> None:
    settings = get_settings()
    admin = db.query(User).filter(User.email == settings.initial_admin_email.lower()).one_or_none()
    if not admin:
        db.add(
            User(
                email=settings.initial_admin_email.lower(),
                full_name=settings.initial_admin_name,
                hashed_password=get_password_hash(settings.initial_admin_password),
                role=Role.admin,
                active=True,
            )
        )
    seed_dictionary_queries(db)
    db.commit()
