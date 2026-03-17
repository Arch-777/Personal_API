import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.db import get_db, set_db_current_user
from api.core.security import decode_access_token
from api.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
	credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
	db: Session = Depends(get_db),
) -> User:
	if credentials is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

	token = credentials.credentials
	try:
		payload = decode_access_token(token)
	except ValueError:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

	user_id = payload.get("sub")
	if not user_id:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

	try:
		parsed_user_id = uuid.UUID(user_id)
	except ValueError:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

	set_db_current_user(db, parsed_user_id)

	user = db.execute(select(User).where(User.id == parsed_user_id)).scalar_one_or_none()
	if user is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

	return user

