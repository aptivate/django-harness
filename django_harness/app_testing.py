from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse, clear_url_caches
from django.dispatch import receiver
from django.template.defaultfilters import date
from django_dynamic_fixture import G
from django.test.utils import override_settings

# Fix URL cache not being cleared between tests
def cms_app_urls_changed(**kwargs):
    # Clear the Django-CMS URL patterns and the root urlconf, which
    # have URLs from the apphook still attached to them, which will
    # break future tests.

    try:
        from cms.views import invalidate_cms_page_cache
        invalidate_cms_page_cache()
    except ImportError as e:
        # doesn't exist in DjangoCMS 2, so ignore this and hope it's not needed
        pass

    clear_url_caches()

    import cms.urls
    reload(cms.urls)

    import urls
    reload(urls)

try:
    from cms.signals import urls_need_reloading
    receiver(urls_need_reloading)(cms_app_urls_changed)
except ImportError as e:
    # doesn't exist in DjangoCMS 2, so ignore this. We'll call it manually
    # when we need it anyway
    pass


class AppTestMixin(object):
    def tearDown(self):
        # Clear the Django-CMS URL patterns and the root urlconf, which
        # have URLs from the apphook still attached to them, which will
        # break future tests.
        # No signal was fired because the page was deleted by rolling back
        # a transaction, not with Page.objects.delete()
        cms_app_urls_changed()
        super(AppTestMixin, self).tearDown()
 
