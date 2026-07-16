from pydantic import BaseModel, ConfigDict


class UserProfileResponse(BaseModel):
    """내 프로필 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str


class UserProfileUpdateRequest(BaseModel):
    """내 프로필 수정 요청 스키마"""

    nickname: str