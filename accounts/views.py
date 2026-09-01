import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

def login_view(request):
    """
    SaaS 로그인 뷰 (이메일 또는 아이디 기반 인증)
    """
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not identifier or not password:
            messages.error(request, '이메일(아이디)과 비밀번호를 모두 입력해 주세요.')
            return render(request, 'accounts/login.html')

        # 1. username으로 먼저 인증 시도
        user = authenticate(request, username=identifier, password=password)
        
        # 2. 실패 시 email로 유저를 찾아 username으로 재시도
        if user is None and '@' in identifier:
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                user = None

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'환영합니다, {user.first_name or user.username}님!')
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                messages.error(request, '비활성화된 계정입니다. 관리자에게 문의하세요.')
        else:
            messages.error(request, '아이디/이메일 또는 비밀번호가 올바르지 않습니다.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    """
    로그아웃 후 로그인 페이지로 리다이렉트
    """
    logout(request)
    messages.info(request, '안전하게 로그아웃되었습니다.')
    return redirect('accounts:login')


@login_required
def change_password_view(request):
    """
    비밀번호 자가 변경 뷰
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not request.user.check_password(current_password):
            messages.error(request, '현재 비밀번호가 일치하지 않습니다.')
            return render(request, 'accounts/change_password.html')

        if len(new_password) < 6:
            messages.error(request, '새 비밀번호는 최소 6자 이상이어야 합니다.')
            return render(request, 'accounts/change_password.html')

        if new_password != confirm_password:
            messages.error(request, '새 비밀번호 확인이 일치하지 않습니다.')
            return render(request, 'accounts/change_password.html')

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)  # 세션 유지
        messages.success(request, '비밀번호가 성공적으로 변경되었습니다.')
        return redirect('/')

    return render(request, 'accounts/change_password.html')


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def user_management_view(request):
    """
    관리자 전용 사용자/팀원 계정 관리 콘솔
    """
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_management.html', {'user_list': users, 'active_tab': 'users'})


@login_required
@user_passes_test(is_admin)
@require_POST
def create_user_api(request):
    """
    신규 사용자 계정 생성 API
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        username = data.get('username', '').strip() or email
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        is_admin_flag = bool(data.get('is_admin', False))

        if not email or not password:
            return JsonResponse({'success': False, 'message': '이메일과 비밀번호는 필수입니다.'}, status=400)

        if User.objects.filter(username__iexact=username).exists():
            return JsonResponse({'success': False, 'message': '이미 존재하는 계정(이메일/아이디)입니다.'}, status=400)

        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'success': False, 'message': '해당 이메일로 등록된 사용자가 이미 있습니다.'}, status=400)

        new_user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name,
            is_staff=is_admin_flag,
            is_superuser=is_admin_flag,
        )

        return JsonResponse({
            'success': True,
            'message': f'계정({new_user.email})이 성공적으로 발급되었습니다.',
            'user': {
                'id': new_user.id,
                'email': new_user.email,
                'username': new_user.username,
                'name': new_user.first_name,
                'is_admin': new_user.is_staff or new_user.is_superuser,
                'date_joined': new_user.date_joined.strftime('%Y-%m-%d %H:%M'),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
@require_POST
def delete_user_api(request, user_id):
    """
    사용자 계정 삭제 API
    """
    if request.user.id == user_id:
        return JsonResponse({'success': False, 'message': '현재 로그인 중인 본인 계정은 삭제할 수 없습니다.'}, status=400)

    try:
        user = User.objects.get(id=user_id)
        user_email = user.email or user.username
        user.delete()
        return JsonResponse({'success': True, 'message': f'계정({user_email})이 성공적으로 삭제되었습니다.'})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': '존재하지 않는 사용자입니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
@require_POST
def reset_user_password_api(request, user_id):
    """
    관리자용 사용자 비밀번호 강제 초기화 API
    """
    try:
        data = json.loads(request.body)
        new_password = data.get('new_password', '').strip()
        
        if not new_password or len(new_password) < 6:
            return JsonResponse({'success': False, 'message': '비밀번호는 최소 6자 이상이어야 합니다.'}, status=400)

        user = User.objects.get(id=user_id)
        user.set_password(new_password)
        user.save()
        return JsonResponse({'success': True, 'message': f'{user.email or user.username}님의 비밀번호가 성공적으로 재설정되었습니다.'})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': '존재하지 않는 사용자입니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
