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
                messages.warning(request, '⏳ 현재 최고관리자(대표님)의 가입 승인 대기 중인 계정입니다. 승인이 완료되면 로그인하실 수 있습니다.')
        else:
            # Django authenticate는 is_active=False일 때 None을 반환하므로 승인 대기 여부를 별도 확인
            try:
                chk_user = User.objects.filter(username__iexact=identifier).first() or User.objects.filter(email__iexact=identifier).first()
                if chk_user and chk_user.check_password(password):
                    if not chk_user.is_active:
                        messages.warning(request, '⏳ 현재 최고관리자(대표님)의 가입 승인 대기 중인 계정입니다. 대표님의 승인이 완료되면 로그인하실 수 있습니다.')
                        return render(request, 'accounts/login.html')
            except Exception:
                pass

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


def register_view(request):
    """
    일반 및 신규 사용자를 위한 가입 승인제 회원가입 뷰
    신규 가입 시 기본적으로 is_active=False(승인 대기) 상태로 생성되며,
    최고관리자(대표님)가 콘솔에서 승인해야 로그인 가능합니다.
    """
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        agree_terms = request.POST.get('agree_terms')

        if not email or not password:
            messages.error(request, '이메일과 비밀번호를 모두 입력해 주세요.')
            return render(request, 'accounts/register.html', {'name': name, 'email': email})

        if '@' not in email or '.' not in email:
            messages.error(request, '유효한 이메일 주소 형식을 입력해 주세요.')
            return render(request, 'accounts/register.html', {'name': name, 'email': email})

        if len(password) < 6:
            messages.error(request, '비밀번호는 안전을 위해 최소 6자 이상이어야 합니다.')
            return render(request, 'accounts/register.html', {'name': name, 'email': email})

        if password != confirm_password:
            messages.error(request, '비밀번호와 비밀번호 확인이 일치하지 않습니다.')
            return render(request, 'accounts/register.html', {'name': name, 'email': email})

        if not agree_terms:
            messages.error(request, '서비스 이용약관 및 개인정보 처리방침에 동의해 주세요.')
            return render(request, 'accounts/register.html', {'name': name, 'email': email})

        # 최고관리자 고유 계정 방어
        if email == 'ethan@ncomputing.com':
            messages.info(request, '최고관리자 전용 계정입니다. 로그인 페이지에서 로그인해 주세요.')
            return redirect('accounts:login')

        # 중복 이메일/아이디 확인
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            messages.error(request, '이미 등록된 이메일 계정입니다. 로그인하거나 다른 이메일을 사용해 주세요.')
            return render(request, 'accounts/register.html', {'name': name, 'email': email})

        # 가입 승인제: is_active=False 로 생성 (대표님 승인 전까지 로그인 차단)
        User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name,
            is_staff=False,
            is_superuser=False,
            is_active=False,
        )

        messages.success(
            request,
            f'🎉 {name or email}님의 가입 신청이 성공적으로 접수되었습니다. '
            f'최고관리자(대표님)의 승인 완료 후 로그인하실 수 있습니다.'
        )
        return redirect('accounts:login')

    return render(request, 'accounts/register.html')


from curation.models import SavedArticle, Keyword, ApiUsage


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@login_required
def admin_dashboard_view(request):
    """
    최고관리자(ethan@ncomputing.com 및 마스터 관리자) 전용 커스텀 관리자 대시보드
    - 일반 유저는 차단 및 안내 후 메인 리다이렉트
    - 총 회원 수, 플랫폼 전체 데이터 개수, 최근 생성 데이터 20건(작성자, 내용) 집계
    """
    is_master = (
        request.user.email.lower() == 'ethan@ncomputing.com' or
        request.user.username.lower() == 'ethan@ncomputing.com' or
        request.user.is_superuser or
        request.user.is_staff
    )
    if not is_master:
        messages.error(request, '최고관리자(대표님) 및 인가된 관리자만 접근할 수 있는 관리자 패널입니다.')
        return redirect('/')

    # 1. 회원 통계 집계
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    pending_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()

    # 2. 플랫폼 전체 데이터 개수 집계 (아카이브 기사 + 키워드)
    total_articles = SavedArticle.objects.count()
    total_keywords = Keyword.objects.count()
    total_all_data = total_articles + total_keywords
    api_stats = ApiUsage.get_current_stats()

    # 3. 가장 최근에 생성된 데이터 20건 (작성자 및 내용 상세)
    recent_20_articles = SavedArticle.objects.select_related('user').order_by('-created_at')[:20]

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'pending_users': pending_users,
        'staff_users': staff_users,
        'total_articles': total_articles,
        'total_keywords': total_keywords,
        'total_all_data': total_all_data,
        'api_stats': api_stats,
        'recent_articles': recent_20_articles,
        'active_tab': 'admin_dashboard',
    }
    return render(request, 'accounts/admin_dashboard.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def user_management_view(request):
    """
    관리자 전용 사용자/팀원 계정 관리 콘솔
    승인 대기자(is_active=False)가 상단에 먼저 표시됩니다.
    """
    users = User.objects.all().order_by('is_active', '-date_joined')
    pending_count = User.objects.filter(is_active=False).count()
    return render(request, 'accounts/user_management.html', {
        'user_list': users,
        'pending_count': pending_count,
        'active_tab': 'users'
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def create_user_api(request):
    """
    신규 사용자 계정 직접 발급 API
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
def toggle_user_role_api(request, user_id):
    """
    관리자용 사용자 권한(운영자 ↔ 일반 회원) 토글 API
    """
    try:
        user = User.objects.get(id=user_id)

        # 최고관리자 계정 보호
        if user.is_superuser or user.email.lower() == 'ethan@ncomputing.com':
            return JsonResponse({'success': False, 'message': '최고관리자 계정의 권한은 변경할 수 없습니다.'}, status=400)

        if request.user.id == user_id:
            return JsonResponse({'success': False, 'message': '현재 로그인 중인 본인의 관리 권한은 직접 변경할 수 없습니다.'}, status=400)

        user.is_staff = not user.is_staff
        user.save(update_fields=['is_staff'])

        role_label = '운영자(Staff)' if user.is_staff else '일반 회원(Standard)'
        return JsonResponse({
            'success': True,
            'is_staff': user.is_staff,
            'message': f'{user.email}님의 권한이 [{role_label}]으로 변경되었습니다.'
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': '존재하지 않는 사용자입니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
@require_POST
def toggle_user_active_api(request, user_id):
    """
    관리자용 사용자 활성/일시정지 상태 토글 API
    """
    try:
        user = User.objects.get(id=user_id)

        # 최고관리자 계정 보호
        if user.is_superuser or user.email.lower() == 'ethan@ncomputing.com':
            return JsonResponse({'success': False, 'message': '최고관리자 계정은 일시정지할 수 없습니다.'}, status=400)

        if request.user.id == user_id:
            return JsonResponse({'success': False, 'message': '현재 로그인 중인 본인 계정은 일시정지할 수 없습니다.'}, status=400)

        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        action_msg = f'{user.email}님의 가입이 성공적으로 승인(활성화)되었습니다.' if user.is_active else f'{user.email}님의 계정이 일시정지되었습니다.'
        return JsonResponse({
            'success': True,
            'is_active': user.is_active,
            'message': action_msg
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': '존재하지 않는 사용자입니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
@require_POST
def delete_user_api(request, user_id):
    """
    사용자 계정 삭제 API (최고관리자 삭제 차단)
    """
    if request.user.id == user_id:
        return JsonResponse({'success': False, 'message': '현재 로그인 중인 본인 계정은 삭제할 수 없습니다.'}, status=400)

    try:
        user = User.objects.get(id=user_id)

        # 최고관리자 계정 영구 보호
        if user.is_superuser or user.email.lower() == 'ethan@ncomputing.com':
            return JsonResponse({'success': False, 'message': '최고관리자 계정은 시스템 보호를 위해 삭제할 수 없습니다.'}, status=400)

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
