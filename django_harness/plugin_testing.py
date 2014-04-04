class PluginTestMixin(object):
    plugin_class = None
    plugin_defaults = {}

    # You need to define plugin_class

    def setUp(self):
        super(PluginTestMixin, self).setUp()

        if self.plugin_class is not None:
            self.plugin = self.plugin_class()

            from cms.models.placeholdermodel import Placeholder
            self.placeholder = Placeholder(slot="main")
            self.placeholder.save()

            self.instance = self.create_plugin_instance(self.plugin_class)

    FAKE_PATH = '/hello'

    def get_plugin_context(self, **kwargs):
        from cms.plugin_rendering import PluginContext
        return PluginContext(
            dict(request=self.get_fake_request(path=self.FAKE_PATH, **kwargs)),
            instance=self.instance, placeholder=self.placeholder,
            current_app=None)

    def create_plugin_instance(self, plugin_class, **kwargs):
        new_kwargs = {}
        new_kwargs.update(self.plugin_defaults)
        new_kwargs.update(kwargs)

        instance = plugin_class.model(plugin_type=plugin_class.__name__, 
            placeholder=self.placeholder, **new_kwargs)
        instance.cmsplugin_ptr = instance
        instance.pk = 1234 # otherwise plugin_meta_context_processor() crashes
        # instance.save()
        return instance

    def render_plugin(self, plugin_instance=None, **kwargs):
        if plugin_instance is None:
            plugin_instance = self.instance
        return plugin_instance.render_plugin(
            context=self.get_plugin_context(**kwargs))

    def prepare_plugin(self, plugin_instance=None, **kwargs):
        if plugin_instance is None:
            plugin_instance = self.instance
        plugin_instance, plugin = plugin_instance.get_plugin_instance()
        placeholder = plugin_instance.placeholder
        context = self.get_plugin_context(**kwargs)
        return plugin.render(context, plugin_instance, placeholder.slot)

