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

        try:
            from pyelasticsearch import ElasticHttpNotFoundError
        except ImportError:
            # If the import fails, then define a dummy exception class.
            # The effect of this is that no exceptions are ignored, because
            # the dummy class is never raised.
            class ElasticHttpNotFoundError: pass

        # Don't swallow all errors, so we can catch the expected ones
        self.backend.silently_fail = False

        try:
            self.backend.clear()
        except ElasticHttpNotFoundError as e:
            # we don't care if the index didn't exist
            pass

        try:
            from haystack.backends.elasticsearch_backend import ElasticsearchSearchBackend
        except ImportError:
            class ElasticsearchSearchBackend: pass

        if isinstance(self.backend, ElasticsearchSearchBackend):
            # Haystack's ElasticSearch backend doesn't provide a sensible API
            # to create the index, and if it doesn't exist then setup() will
            # fail, so we need to do it ourselves.
            self.backend.conn.create_index(self.backend.index_name,
                self.backend.DEFAULT_SETTINGS)
            unified_index = connections[self.backend.connection_alias].get_unified_index()
            self.content_field_name, field_mapping = self.backend.build_schema(unified_index.all_searchfields())
            current_mapping = {
                'modelresult': {
                    'properties': field_mapping,
                    '_boost': {
                        'name': 'boost',
                        'null_value': 1.0
                    }
                }
            }
            self.backend.conn.put_mapping(self.backend.index_name,
                'modelresult', current_mapping)
            self.backend.silently_fail = True
            self.backend.setup()
            self.backend.silently_fail = False
        else:
            self.backend.setup()

    def get_search_index(self, model_class):
        search_conn = connections[DEFAULT_ALIAS]
        unified_index = search_conn.get_unified_index()
        return unified_index.get_index(model_class)


