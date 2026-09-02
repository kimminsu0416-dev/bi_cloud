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

    if created:
        # 최초 생성 시에만 초기 비밀번호 설정
        user.set_password(password)
        user.save()
        print(f"[SUCCESS] 신규 마스터 계정 생성 완료: {email} / (초기 비번: {password})")
    else:
        # 기존 계정이 있을 때는 권한 및 활성화 상태만 보장하고, 사용자가 변경한 비밀번호는 보존함
        user.email = email
        user.first_name = name
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save(update_fields=['email', 'first_name', 'is_staff', 'is_superuser', 'is_active'])
        print(f"[INFO] 기존 마스터 계정 확인 및 권한 유지 (사용자 지정 비밀번호 보존): {email}")

if __name__ == "__main__":
    create_initial_users()
