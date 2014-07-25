from django.conf import settings

from haystack import connections
from haystack.constants import DEFAULT_ALIAS
from haystack.exceptions import MissingDependency

class WhooshTestMixin(object):
    def _pre_setup(self):
        """
        We need to change the Haystack configuration before fixtures are
        loaded, otherwise they end up in the developer's index and not the
        temporary test index, which is bad for both developers and tests.
        
        This is an internal interface and its use is not recommended.
        """

        super(WhooshTestMixin, self)._pre_setup()

        # Too late to change the backend setup by changing the configuration,
        # so we have to use underhand methods.
        self.search_conn = connections[DEFAULT_ALIAS]
        # self.search_conn.get_backend().use_file_storage = False
        self.backend = self.search_conn.get_backend()

        try:
            from haystack.backends.whoosh_backend import WhooshSearchBackend
        except MissingDependency as e:
            class WhooshSearchBackend(object):
                pass # create a fake one that will never match

        if isinstance(self.backend, WhooshSearchBackend):
            self.backend.path = '/dev/shm/whoosh'
        elif not self.backend.index_name.startswith("test_"):
            self.backend.index_name = "test_" + self.backend.index_name

        self.backend.silently_fail = False
        self.backend.clear()
        self.backend.setup()

    def get_search_index(self, model_class):
        search_conn = connections[DEFAULT_ALIAS]
        unified_index = search_conn.get_unified_index()
        return unified_index.get_index(model_class)


