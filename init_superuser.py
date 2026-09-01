import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

def create_initial_users():
    # 마스터 관리자 계정 (ethan@ncomputing.com / ncom1234)
    email = "ethan@ncomputing.com"
    username = "ethan@ncomputing.com"
    password = "ncom1234"
    name = "Ethan Kim"

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": name,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        }
    )

    # 비밀번호 초기화/보장
    user.set_password(password)
    user.email = email
    user.first_name = name
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()

    if created:
        print(f"[SUCCESS] 신규 마스터 계정 생성 완료: {email} / (초기 비번: {password})")
    else:
        print(f"[SUCCESS] 기존 마스터 계정 업데이트 완료: {email} / (비번: {password})")

if __name__ == "__main__":
    create_initial_users()
