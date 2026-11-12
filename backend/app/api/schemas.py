from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.security.passwords import password_policy_errors


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    department: str
    roles: list[str]
    permissions: list[str] = []


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(max_length=128)
    department_code: str
    roles: list[str] = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        errors = password_policy_errors(v)
        if errors:
            raise ValueError("password needs: " + ", ".join(errors))
        return v


class Page(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int
