from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AccessScope, ExpectedReport, Role, User
from app.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    subject = decode_access_token(token)
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    user = db.query(User).filter(User.email == subject).one_or_none()
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


def require_roles(*roles: Role) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


def user_can_access_report(db: Session, user: User, report: ExpectedReport, write: bool = False) -> bool:
    if user.role in {Role.admin, Role.engineer}:
        return True
    customer_id = report.customer_project.customer_id
    project_id = report.customer_project.project_id
    query = db.query(AccessScope).filter(AccessScope.user_id == user.id)
    if write:
        query = query.filter(AccessScope.can_write.is_(True))
    scopes = query.all()
    return any(
        (scope.customer_id is None or scope.customer_id == customer_id)
        and (scope.project_id is None or scope.project_id == project_id)
        for scope in scopes
    )


def require_report_access(db: Session, user: User, report: ExpectedReport, write: bool = False) -> None:
    if not user_can_access_report(db, user, report, write=write):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Report is outside user access scope")

