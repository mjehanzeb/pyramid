import warnings

from zope.component import queryMultiAdapter
from zope.component import queryUtility
from zope.interface import implements

from repoze.bfg.interfaces import IAuthenticationPolicy
from repoze.bfg.interfaces import IAuthorizationPolicy
from repoze.bfg.interfaces import IViewPermission
from repoze.bfg.interfaces import IViewPermissionFactory

Everyone = 'system.Everyone'
Authenticated = 'system.Authenticated'
Allow = 'Allow'
Deny = 'Deny'

class AllPermissionsList(object):
    """ Stand in 'permission list' to represent all permissions """
    def __iter__(self):
        return ()
    def __contains__(self, other):
        return True
    def __eq__(self, other):
        return isinstance(other, self.__class__)

ALL_PERMISSIONS = AllPermissionsList()
DENY_ALL = (Deny, Everyone, ALL_PERMISSIONS)

def has_permission(permission, context, request):
    """ Provided a permission (a string or unicode object), a context
    (a model instance) and a request object, return an instance of
    ``Allowed`` if the permission is granted in this context to the
    user implied by the request. Return an instance of ``Denied`` if
    this permission is not granted in this context to this user.  This
    function delegates to the current authentication and authorization
    policies.  Return ``Allowed`` unconditionally if no authentication
    policy has been configured in this application."""
    authn_policy = queryUtility(IAuthenticationPolicy)
    if authn_policy is None:
        return Allowed('No authentication policy in use.')

    authz_policy = queryUtility(IAuthorizationPolicy)
    if authz_policy is None:
        raise ValueError('Authentication policy registered without '
                         'authorization policy') # should never happen
    principals = authn_policy.effective_principals(context, request)
    return authz_policy.permits(context, principals, permission)

def authenticated_userid(*args):
    """ Return the userid of the currently authenticated user or
    ``None`` if there is no authentication policy in effect or there
    is no currently authenticated user. """

    largs = len(args)
    if largs > 2:
        raise TypeError(args)
    if largs == 1:
        request = args[0]
        context = None
        warnings.warn(
            'As of BFG 0.9, the "repoze.bfg.security.authenticated_userid" '
            'API now takes two arguments: "context" and "request". '
            'It is being called it with a single argument'
            '(assumed to be a request).   In a future version, the '
            '"authenticated_userid API will stop accepting calls with a '
            'single argument; please fix the calling code.',
            stacklevel=2)
    else:
        context, request = args
        
    policy = queryUtility(IAuthenticationPolicy)
    if policy is None:
        return None
    return policy.authenticated_userid(context, request)

def effective_principals(*args):
    """ Return the list of 'effective' principal identifiers for the
    request.  This will include the userid of the currently
    authenticated user if a user is currently authenticated. If no
    authentication policy is in effect, this will return an empty
    sequence."""

    largs = len(args)
    if largs > 2:
        raise TypeError(args)
    if largs == 1:
        request = args[0]
        context = None
        warnings.warn(
            'As of BFG 0.9, the "repoze.bfg.security.effective_principals " '
            'API now takes two arguments: "context" and "request". '
            'It is being called it with a single argument'
            '(assumed to be a request).   In a future version, the '
            '"effective_principals API will stop accepting calls with a '
            'single argument; please fix the calling code.',
            stacklevel=2)
    else:
        context, request = args
        
    policy = queryUtility(IAuthenticationPolicy)
    if policy is None:
        return []
    return policy.effective_principals(context, request)

def principals_allowed_by_permission(context, permission):
    """ Provided a context (a model object), and a permission (a
    string or unicode object), return a sequence of principal ids that
    possess the permission in the context.  If no authorization policy
    is in effect, this will return a sequence with the single value
    representing ``Everyone`` (the special principal identifier
    representing all principals).

    .. note:: even if an authorization policy *is* in effect, some
       (exotic) authorization policies may not implement the required
       machinery for this function; those will cause a
       ``NotImplementedError`` exception to be raised when this
       function is invoked.
    """
    policy = queryUtility(IAuthorizationPolicy)
    if policy is None:
        return [Everyone]
    return policy.principals_allowed_by_permission(context, permission)

def view_execution_permitted(context, request, name=''):
    """ If the view specified by ``context`` and ``name`` is protected
    by a permission, check the permission associated with the view
    using the effective authentication/authorization policies and the
    ``request``.  Return a boolean result.  If no authentication
    policy is in effect, or if the view is not protected by a
    permission, return True."""
    result = queryMultiAdapter((context, request), IViewPermission,
                               name=name, default=None)
    if result is None:
        return Allowed(
            'Allowed: view name %r in context %r (no permission defined)' %
            (name, context))
    return result

def remember(context, request, principal, **kw):
    """ Return a sequence of header tuples (e.g. ``[('Set-Cookie',
    'foo=abc')]``) suitable for 'remembering' a set of credentials
    implied by the data passed as ``principal`` and ``*kw`` using the
    current authentication policy.  Common usage might look like so
    within the body of a view function (``response`` is assumed to be
    an WebOb-style response object computed previously by the view
    code)::

      from repoze.bfg.security import forget
      headers = remember(context, request, 'chrism', password='123')
      response.headerlist.extend(headers)
      return response

    If no authentication policy is in use, this function will always
    return an empty sequence.  If used, the composition and meaning of
    ``**kw`` must be agreed upon by the calling code and the effective
    authentication policy."""
    policy = queryUtility(IAuthenticationPolicy)
    if policy is None:
        return []
    else:
        return policy.remember(context, request, principal, **kw)

def forget(context, request):
    """ Return a sequence of header tuples (e.g. ``[('Set-Cookie',
    'foo=abc')]``) suitable for 'forgetting' the set of credentials
    possessed by the currently authenticated user.  A common usage
    might look like so within the body of a view function
    (``response`` is assumed to be an WebOb-style response object
    computed previously by the view code)::

      from repoze.bfg.security import forget
      headers = forget(context, request)
      response.headerlist.extend(headers)
      return response

    If no authentication policy is in use, this function will always
    return an empty sequence."""
    policy = queryUtility(IAuthenticationPolicy)
    if policy is None:
        return []
    else:
        return policy.forget(context, request)
    
class PermitsResult(int):
    def __new__(cls, s, *args):
        inst = int.__new__(cls, cls.boolval)
        inst.s = s
        inst.args = args
        return inst
        
    @property
    def msg(self):
        return self.s % self.args

    def __str__(self):
        return self.msg

    def __repr__(self):
        return '<%s instance at %s with msg %r>' % (self.__class__.__name__,
                                                    id(self),
                                                    self.msg)

class Denied(PermitsResult):
    """ An instance of ``Denied`` is returned when a security-related
    API or other ``repoze.bfg`` code denies an action unlrelated to an
    ACL check.  It evaluates equal to all boolean false types.  It has
    an attribute named ``msg`` describing the circumstances for the
    deny."""
    boolval = 0

class Allowed(PermitsResult):
    """ An instance of ``Allowed`` is returned when a security-related
    API or other ``repoze.bfg`` code allows an action unrelated to an
    ACL check.  It evaluates equal to all boolean true types.  It has
    an attribute named ``msg`` describing the circumstances for the
    allow."""
    boolval = 1

class ACLPermitsResult(int):
    def __new__(cls, ace, acl, permission, principals, context):
        inst = int.__new__(cls, cls.boolval)
        inst.permission = permission
        inst.ace = ace
        inst.acl = acl
        inst.principals = principals
        inst.context = context
        return inst

    @property
    def msg(self):
        s = ('%s permission %r via ACE %r in ACL %r on context %r for '
             'principals %r')
        return s % (self.__class__.__name__,
                    self.permission,
                    self.ace,
                    self.acl,
                    self.context,
                    self.principals)

    def __str__(self):
        return self.msg

    def __repr__(self):
        return '<%s instance at %s with msg %r>' % (self.__class__.__name__,
                                                    id(self),
                                                    self.msg)

class ACLDenied(ACLPermitsResult):
    """ An instance of ``ACLDenied`` represents that a security check
    made explicitly against ACL was denied.  It evaluates equal to all
    boolean false types.  It also has attributes which indicate which
    acl, ace, permission, principals, and context were involved in the
    request.  Its __str__ method prints a summary of these attributes
    for debugging purposes.  The same summary is available as the
    ``msg`` attribute."""
    boolval = 0

class ACLAllowed(ACLPermitsResult):
    """ An instance of ``ACLDenied`` represents that a security check
    made explicitly against ACL was allowed.  It evaluates equal to
    all boolean true types.  It also has attributes which indicate
    which acl, ace, permission, principals, and context were involved
    in the request.  Its __str__ method prints a summary of these
    attributes for debugging purposes.  The same summary is available
    as the ``msg`` attribute."""
    boolval = 1

class ViewPermissionFactory(object):
    implements(IViewPermissionFactory)

    def __init__(self, permission_name):
        self.permission_name = permission_name

    def __call__(self, context, request):
        return has_permission(self.permission_name, context, request)
        
class Unauthorized(Exception):
    pass

# BBB imports: these must come at the end of the file, as there's a
# circular dependency between secpols and security
from repoze.bfg.secpols import ACLSecurityPolicy
from repoze.bfg.secpols import InheritingACLSecurityPolicy
from repoze.bfg.secpols import RemoteUserACLSecurityPolicy
from repoze.bfg.secpols import RemoteUserInheritingACLSecurityPolicy
from repoze.bfg.secpols import WhoACLSecurityPolicy
from repoze.bfg.secpols import WhoInheritingACLSecurityPolicy
# /BBB imports

