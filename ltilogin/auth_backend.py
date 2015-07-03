from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
import logging


logger = logging.getLogger('radar.ltilogin')


class LTIAuthBackend(ModelBackend):
    """
    Authenticates the trusted user from the LTI request.
    
    """
    def authenticate(self, oauth_request=None):
        if not oauth_request:
            return None
        if not oauth_request.user_id:
            logger.warning('LTI login attempt without a user id.')
            return None
        
        username = oauth_request.user_id[:30]
        email = oauth_request.lis_person_contact_email_primary \
            if oauth_request.lis_person_contact_email_primary[:254] else ''
        first_name = oauth_request.lis_person_name_given \
            if oauth_request.lis_person_name_given[:30] else ''
        last_name = oauth_request.lis_person_name_family \
            if oauth_request.lis_person_name_family[:30] else ''
        roles = set(oauth_request.roles.split(',') if oauth_request.roles else ())

        if hasattr(settings, 'LTI_ACCEPTED_ROLES') and roles.isdisjoint(settings.LTI_ACCEPTED_ROLES):
            logger.warning('LTI login attempt without accepted user role: %s', roles)
            return None
        
        staff = hasattr(settings, 'LTI_STAFF_ROLES') and not roles.isdisjoint(settings.LTI_STAFF_ROLES)

        UserModel = get_user_model()
        user = UserModel._default_manager.filter(username=username).first()
        if not user:
            logger.info('Creating a new LTI authenticated user: %s', username)
            user = UserModel._default_manager.create_user(username, email, first_name=first_name, last_name=last_name)
            user.set_unusable_password()
            user.save()
        if staff != user.is_staff:
            logger.info('Adjusting LTI authenticated user to staff=%s: %s', staff, username)
            user.is_staff = staff
            user.save()
        return user
